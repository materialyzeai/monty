"""Microbenchmarks for hot paths in monty.

Run with ``pytest tests/test_benchmarks.py --benchmark-only`` (skipped from the
default test run via ``-m "not benchmark"`` if you want to filter).

The benchmarks target call sites that appear in tight loops in downstream
libraries (pymatgen, matgl, matcalc). Numbers should only be compared on the
same machine across commits.
"""

from __future__ import annotations

import importlib
import json
from typing import TYPE_CHECKING

import numpy as np
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from monty.collections import AttrDict, frozendict
from monty.design_patterns import cached_class
from monty.dev import deprecated
from monty.fnmatch import WildCard
from monty.fractions import gcd, lcm
from monty.inspect import caller_name
from monty.io import reverse_readline, zopen
from monty.itertools import iuptri
from monty.json import MontyDecoder, MontyEncoder, MSONable, jsanitize
from monty.math import nCr, nPr
from monty.os.path import find_exts, zpath
from monty.re import regrep
from monty.serialization import dumpfn, loadfn
from monty.string import is_string, list_strings

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------


class _Sample(MSONable):
    def __init__(self, a: int, b: str, c: list) -> None:
        self.a = a
        self.b = b
        self.c = c


@pytest.fixture
def sample_obj() -> _Sample:
    return _Sample(a=1, b="hello", c=[1, 2, 3, 4, 5])


@pytest.fixture
def sample_dict() -> dict:
    return {
        "a": 1,
        "b": "string",
        "c": [1, 2, 3, 4, 5],
        "d": {"nested": [{"x": i, "y": i * 2} for i in range(20)]},
        "e": [{"k": v} for v in range(20)],
    }


@pytest.fixture
def large_array() -> np.ndarray:
    return np.arange(10_000, dtype=np.float64)


@pytest.fixture
def big_dir(tmp_path: Path) -> Path:
    for i in range(50):
        sub = tmp_path / f"sub{i}"
        sub.mkdir()
        for j in range(20):
            (sub / f"file{j}.txt").write_text("x")
            (sub / f"file{j}.log").write_text("x")
    return tmp_path


@pytest.fixture
def big_log(tmp_path: Path) -> Path:
    p = tmp_path / "big.log"
    with p.open("w") as f:
        for i in range(20_000):
            f.write(f"line {i} energy = {i * 0.001}\n")
    return p


# -------------------------------------------------------------------------
# Import cost
# -------------------------------------------------------------------------


def test_bench_import_monty_json(benchmark):
    def _reimport():
        # Drop from sys.modules so the import body re-runs.
        import sys

        for k in list(sys.modules):
            if k == "monty.json" or k.startswith("monty.json."):
                del sys.modules[k]
        importlib.import_module("monty.json")

    benchmark(_reimport)


# -------------------------------------------------------------------------
# json / MSONable hot paths
# -------------------------------------------------------------------------


def test_bench_as_dict(benchmark, sample_obj):
    benchmark(sample_obj.as_dict)


def test_bench_to_json(benchmark, sample_obj):
    benchmark(sample_obj.to_json)


def test_bench_from_dict(benchmark, sample_obj):
    d = sample_obj.as_dict()
    benchmark(_Sample.from_dict, d)


def test_bench_montyencoder_default_ndarray(benchmark, large_array):
    encoder = MontyEncoder()
    benchmark(encoder.default, large_array)


def test_bench_montydecoder_process(benchmark, sample_dict):
    decoder = MontyDecoder()
    benchmark(decoder.process_decoded, sample_dict)


def test_bench_jsanitize_plain(benchmark, sample_dict):
    benchmark(jsanitize, sample_dict)


def test_bench_jsanitize_strict_ndarray(benchmark, large_array):
    benchmark(jsanitize, large_array)


# -------------------------------------------------------------------------
# math / fractions
# -------------------------------------------------------------------------


def test_bench_nCr_large(benchmark):
    benchmark(nCr, 200, 100)


def test_bench_nPr_large(benchmark):
    benchmark(nPr, 200, 100)


def test_bench_gcd_many(benchmark):
    nums = list(range(2, 50))
    benchmark(gcd, *nums)


def test_bench_lcm_many(benchmark):
    nums = list(range(2, 30))
    benchmark(lcm, *nums)


# -------------------------------------------------------------------------
# string
# -------------------------------------------------------------------------


def test_bench_is_string_true(benchmark):
    benchmark(is_string, "hello world")


def test_bench_is_string_false(benchmark):
    benchmark(is_string, 12345)


def test_bench_list_strings_list(benchmark):
    args = [f"item{i}" for i in range(50)]
    benchmark(list_strings, args)


# -------------------------------------------------------------------------
# itertools
# -------------------------------------------------------------------------


def test_bench_iuptri(benchmark):
    items = list(range(40))
    benchmark(lambda: list(iuptri(items)))


# -------------------------------------------------------------------------
# collections
# -------------------------------------------------------------------------


def test_bench_attrdict_set(benchmark):
    d = AttrDict()

    def _set():
        for i in range(100):
            d[f"k{i}"] = i

    benchmark(_set)


def test_bench_frozendict_init(benchmark):
    items = {f"k{i}": i for i in range(100)}
    benchmark(frozendict, items)


# -------------------------------------------------------------------------
# design_patterns
# -------------------------------------------------------------------------


def test_bench_cached_class_init(benchmark):
    @cached_class
    class C:
        def __init__(self, a, b=2, c=3):
            self.a, self.b, self.c = a, b, c

    counter = [0]

    def _make():
        counter[0] += 1
        return C(counter[0])

    benchmark(_make)


# -------------------------------------------------------------------------
# dev
# -------------------------------------------------------------------------


def test_bench_deprecated_call(benchmark, recwarn):
    @deprecated(message="use new_func instead")
    def old_func(x, y):
        return x + y

    benchmark(old_func, 1, 2)


# -------------------------------------------------------------------------
# fnmatch
# -------------------------------------------------------------------------


def test_bench_wildcard_match(benchmark):
    w = WildCard("*.nc|*.pdf|*.txt|*.log")
    names = [f"file{i}.{ext}" for i in range(50) for ext in ("nc", "pdf", "tmp", "log")]
    benchmark(w.filter, names)


# -------------------------------------------------------------------------
# os.path
# -------------------------------------------------------------------------


def test_bench_find_exts(benchmark, big_dir):
    benchmark(find_exts, str(big_dir), ["txt"])


def test_bench_zpath(benchmark, tmp_path):
    f = tmp_path / "data.json"
    f.write_text("{}")
    target = str(f)
    benchmark(zpath, target)


# -------------------------------------------------------------------------
# re
# -------------------------------------------------------------------------


def test_bench_regrep(benchmark, big_log):
    patterns = {"energy": r"energy = ([\d\.]+)"}
    benchmark(regrep, str(big_log), patterns)


def test_bench_regrep_terminate(benchmark, big_log):
    patterns = {"energy": r"energy = ([\d\.]+)"}
    benchmark(regrep, str(big_log), patterns, terminate_on_match=True)


# -------------------------------------------------------------------------
# inspect
# -------------------------------------------------------------------------


def test_bench_caller_name(benchmark):
    def caller():
        return caller_name(skip=2)

    benchmark(caller)


# -------------------------------------------------------------------------
# serialization
# -------------------------------------------------------------------------


def test_bench_dumpfn_jsonl(benchmark, tmp_path):
    objs = [{"i": i, "x": list(range(10))} for i in range(200)]
    p = tmp_path / "out.jsonl"

    def _dump():
        if p.exists():
            p.unlink()
        dumpfn(objs, p)

    benchmark(_dump)


def test_bench_loadfn_yaml(benchmark, tmp_path):
    p = tmp_path / "data.yaml"
    p.write_text("a: 1\nb: 2\nc:\n  - 1\n  - 2\n  - 3\n")
    benchmark(loadfn, p)


# -------------------------------------------------------------------------
# io
# -------------------------------------------------------------------------


def test_bench_reverse_readline(benchmark, big_log):
    def _read():
        with zopen(big_log, mode="rt", encoding="utf-8") as f:
            for _ in reverse_readline(f, max_mem=4096):
                pass

    benchmark(_read)
