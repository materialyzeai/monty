from __future__ import annotations

import datetime
import glob
import json
import os
import pathlib

import numpy as np
import pytest

from monty.json import MSONable, TypeHandler, register, unregister
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

    def test_yaml_msonable_roundtrip(self, tmp_dir):
        """MSONable subclasses round-trip through YAML (issue #587)."""
        obj = toyMsonable(a=7, b="seven")
        dumpfn(obj, "monte_test.yaml")
        reloaded = loadfn("monte_test.yaml")
        assert isinstance(reloaded, toyMsonable)
        assert reloaded == obj

        # Nested inside list and dict.
        nested = {"items": [toyMsonable(a=i, b=str(i)) for i in range(3)]}
        dumpfn(nested, "monte_test.yaml")
        reloaded = loadfn("monte_test.yaml")
        assert all(isinstance(o, toyMsonable) for o in reloaded["items"])
        assert reloaded["items"] == nested["items"]

        # ``cls=None`` opts out of reconstruction, mirroring the JSON path.
        raw = loadfn("monte_test.yaml", cls=None)
        assert isinstance(raw["items"][0], dict)
        assert raw["items"][0]["@class"] == "toyMsonable"

    def test_yaml_numpy_path_roundtrip(self, tmp_dir):
        """numpy arrays and pathlib paths round-trip through YAML."""
        payload = {
            "arr": np.array([1.0, 2.0, 3.0]),
            "p": pathlib.Path("/tmp/example"),
        }
        dumpfn(payload, "monte_test.yaml")
        reloaded = loadfn("monte_test.yaml")
        assert isinstance(reloaded["arr"], np.ndarray)
        np.testing.assert_array_equal(reloaded["arr"], payload["arr"])
        assert isinstance(reloaded["p"], pathlib.PurePath)
        assert reloaded["p"] == payload["p"]

    def test_yaml_preserves_native_datetime(self, tmp_dir):
        """datetime keeps ruamel.yaml's native rendering (no @module envelope)."""
        when = datetime.datetime(2026, 5, 18, 12, 0, 0)
        dumpfn({"when": when}, "monte_test.yaml")
        with open("monte_test.yaml", encoding="utf-8") as f:
            raw = f.read()
        # Native ruamel.yaml emits the timestamp as a bare scalar, not as a
        # ``@module``/``@class`` envelope.
        assert "@module" not in raw
        assert "2026-05-18" in raw
        reloaded = loadfn("monte_test.yaml")
        assert reloaded["when"] == when

    def test_yaml_plain_dict_unchanged(self, tmp_dir):
        """Plain dict YAML output is byte-identical to pre-#587 behavior."""
        dumpfn({"hello": "world"}, "monte_test.yaml")
        with open("monte_test.yaml", encoding="utf-8") as f:
            raw = f.read()
        assert raw == "hello: world\n"

    def test_yaml_user_typehandler(self, tmp_dir):
        """User-registered TypeHandlers participate in YAML round-trip."""

        class MyType:
            def __init__(self, value: int):
                self.value = value

            def __eq__(self, other):
                return isinstance(other, MyType) and self.value == other.value

        class MyHandler(TypeHandler):
            module = "tests.test_serialization"
            class_name = "MyType"

            def matches(self, obj):
                return isinstance(obj, MyType)

            def encode(self, obj):
                return {
                    "@module": self.module,
                    "@class": self.class_name,
                    "value": obj.value,
                }

            def decode(self, d):
                return MyType(d["value"])

        handler = MyHandler()
        register(handler)
        try:
            obj = MyType(42)
            dumpfn(obj, "monte_test.yaml")
            reloaded = loadfn("monte_test.yaml")
            assert isinstance(reloaded, MyType)
            assert reloaded == obj
        finally:
            unregister(handler)
