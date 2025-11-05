from __future__ import annotations

import glob
import json
import os

import pytest

from monty.json import MSONable
from monty.serialization import dumpfn, loadfn
from monty.tempfile import ScratchDir

try:
    import msgpack
except ImportError:
    msgpack = None


class toyMsonable(MSONable):
    """Dummy class to test de-/serialization."""

    def __init__(self, a: int, b: str):
        self.a = a
        self.b = b

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return all(
            hasattr(other, attr) and getattr(other, attr, None) == getattr(self, attr)
            for attr in {"a", "b"}
        )


class TestSerial:
    @classmethod
    def teardown_class(cls):
        # Cleans up test files if a test fails
        files_to_clean_up = glob.glob("monte_test.*")
        for fn in files_to_clean_up:
            os.remove(fn)

    def test_dumpfn_loadfn(self, tmp_dir):
        d = {"hello": "world"}

        # Test standard configuration
        for ext in (
            "json",
            "yaml",
            "yml",
            "json.gz",
            "yaml.gz",
            "json.bz2",
            "yaml.bz2",
        ):
            fn = f"monte_test.{ext}"
            dumpfn(d, fn)
            d2 = loadfn(fn)
            assert d == d2, f"Test file with extension {ext} did not parse correctly"

        # Test custom kwarg configuration
        dumpfn(d, "monte_test.json", indent=4)
        d2 = loadfn("monte_test.json")
        assert d == d2
        dumpfn(d, "monte_test.yaml")
        d2 = loadfn("monte_test.yaml")
        assert d == d2

        # Check if fmt override works.
        dumpfn(d, "monte_test.json", fmt="yaml")
        with pytest.raises(json.decoder.JSONDecodeError):
            loadfn("monte_test.json")
        d2 = loadfn("monte_test.json", fmt="yaml")
        assert d == d2

        with pytest.raises(TypeError):
            dumpfn(d, "monte_test.txt", fmt="garbage")
        with pytest.raises(TypeError):
            loadfn("monte_test.txt", fmt="garbage")

    @pytest.mark.skipif(msgpack is None, reason="msgpack-python not installed.")
    def test_mpk(self, tmp_dir):
        d = {"hello": "world"}

        # Test automatic format detection
        dumpfn(d, "monte_test.mpk")
        d2 = loadfn("monte_test.mpk")
        assert d == d2

        # Test to ensure basename is respected, and not directory
        with ScratchDir("."):
            os.mkdir("mpk_test")
            os.chdir("mpk_test")
            fname = os.path.abspath("test_file.json")
            dumpfn({"test": 1}, fname)
            with open("test_file.json", encoding="utf-8") as f:
                reloaded = json.loads(f.read())
            assert reloaded["test"] == 1

    def test_json_lines(self, tmp_dir):
        d = [
            {"obj": toyMsonable(a=i, b=str(i)), "other": 1.0, "stuff": {"c": 3, "d": 4}}
            for i in range(5)
        ]
        dumpfn(d, "monte_test.jsonl.gz")
        new_d = loadfn("monte_test.jsonl.gz")
        assert all(new_d[i] == entry for i, entry in enumerate(d))
        assert all(isinstance(entry["obj"], toyMsonable) for entry in new_d)

        new_d = loadfn("monte_test.jsonl.gz", cls=None)
        assert all(
            isinstance(entry["obj"], dict)
            and toyMsonable.from_dict(entry["obj"]) == d[i]["obj"]
            for i, entry in enumerate(new_d)
        )
