from __future__ import annotations

import dataclasses
import datetime
import json
import os
import pathlib
from enum import Enum
from typing import Union

import numpy as np
import pytest

from monty.json import (
    MontyDecoder,
    MontyEncoder,
    MSONable,
    _check_type,
    _load_redirect,
    jsanitize,
    load,
    load2dict,
    partial_monty_encode,
    save,
)

from . import __version__ as TESTS_VERSION

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import pint
except ImportError:
    pint = None

try:
    import torch
except ImportError:
    torch = None

try:
    import pydantic
except ImportError:
    pydantic = None

try:
    from bson.objectid import ObjectId
except ImportError:
    ObjectId = None

try:
    from bson import json_util
except ImportError:
    json_util = None


TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_files")


class GoodMSONClass(MSONable):
    def __init__(self, a, b, c, d=1, *values, **kwargs):
        self.a = a
        self.b = b
        self._c = c
        self._d = d
        self.values = values
        self.kwargs = kwargs

    def __eq__(self, other):
        return (
            self.a == other.a
            and self.b == other.b
            and self._c == other._c
            and self._d == other._d
            and self.kwargs == other.kwargs
            and self.values == other.values
        )


class GoodNOTMSONClass:
    """Literally the same as the GoodMSONClass, except it does not have
    the MSONable inheritance!"""

    def __init__(self, a, b, c, d=1, *values, **kwargs):
        self.a = a
        self.b = b
        self._c = c
        self._d = d
        self.values = values
        self.kwargs = kwargs

    def __eq__(self, other):
        return (
            self.a == other.a
            and self.b == other.b
            and self._c == other._c
            and self._d == other._d
            and self.kwargs == other.kwargs
            and self.values == other.values
        )


class LimitedMSONClass(MSONable):
    """An MSONable class that only accepts a limited number of options"""

    def __init__(self, a):
        self.a = a

    def __eq__(self, other):
        return self.a == other.a


class GoodNestedMSONClass(MSONable):
    def __init__(self, a_list, b_dict, c_list_dict_list, **kwargs):
        assert isinstance(a_list, list)
        assert isinstance(b_dict, dict)
        assert isinstance(c_list_dict_list, list)
        assert isinstance(c_list_dict_list[0], dict)
        first_key = next(iter(c_list_dict_list[0]))
        assert isinstance(c_list_dict_list[0][first_key], list)
        self.a_list = a_list
        self.b_dict = b_dict
        self._c_list_dict_list = c_list_dict_list
        self.kwargs = kwargs


class MethodSerializationClass(MSONable):
    def __init__(self, a):
        self.a = a

    def method(self):
        pass

    @staticmethod
    def staticmethod(self):
        pass

    @classmethod
    def classmethod(cls):
        pass

    def __call__(self, b):
        # override call for instances
        return self.__class__(b)

    class NestedClass:
        def inner_method(self):
            pass


class MethodNonSerializationClass:
    def __init__(self, a):
        self.a = a

    def method(self):
        pass


def my_callable(a, b):
    return a + b


class EnumNoAsDict(Enum):
    name_a = "value_a"
    name_b = "value_b"


class EnumAsDict(Enum):
    name_a = "value_a"
    name_b = "value_b"

    def as_dict(self):
        return {"v": self.value}

    @classmethod
    def from_dict(cls, d):
        return cls(d["v"])


class EnumTest(MSONable, Enum):
    a = 1
    b = 2


class ClassContainingDataFrame(MSONable):
    def __init__(self, df):
        self.df = df


class ClassContainingSeries(MSONable):
    def __init__(self, s):
        self.s = s


class ClassContainingQuantity(MSONable):
    def __init__(self, qty):
        self.qty = qty


class ClassContainingNumpyArray(MSONable):
    def __init__(self, np_a):
        self.np_a = np_a


@dataclasses.dataclass
class Point:
    x: float = 1
    y: float = 2


class Coordinates(MSONable):
    def __init__(self, points):
        self.points = points

    def __str__(self):
        return str(self.points)


@dataclasses.dataclass
class NestedDataClass:
    points: list[Point]


class TestMSONable:
    def setup_method(self):
        self.good_cls = GoodMSONClass

        class BadMSONClass(MSONable):
            def __init__(self, a, b):
                self.a = a
                self.b = b

            def as_dict(self):
                return {"init": {"a": self.a, "b": self.b}}

        self.bad_cls = BadMSONClass

        class BadMSONClass2(MSONable):
            def __init__(self, a, b):
                self.a = a
                self.c = b

        self.bad_cls2 = BadMSONClass2

        class AutoMSON(MSONable):
            def __init__(self, a, b):
                self.a = a
                self.b = b

        self.auto_mson = AutoMSON

        class ClassContainingKWOnlyArgs(MSONable):
            def __init__(self, *, a):
                self.a = a

        self.kw_only_args_cls = ClassContainingKWOnlyArgs

    def test_to_from_dict(self):
        obj = self.good_cls("Hello", "World", "Python")
        d = obj.as_dict()
        assert d is not None
        self.good_cls.from_dict(d)
        jsonstr = obj.to_json()
        d = json.loads(jsonstr)
        assert d["@class"], "GoodMSONClass"
        obj = self.bad_cls("Hello", "World")
        d = obj.as_dict()
        assert d is not None
        with pytest.raises(TypeError):
            self.bad_cls.from_dict(d)
        obj = self.bad_cls2("Hello", "World")
        with pytest.raises(NotImplementedError):
            obj.as_dict()
        obj = self.auto_mson(2, 3)
        d = obj.as_dict()
        self.auto_mson.from_dict(d)

    def test_kw_only_args(self):
        obj = self.kw_only_args_cls(a=1)
        d = obj.as_dict()
        assert d is not None
        assert d["a"] == 1
        self.kw_only_args_cls.from_dict(d)
        jsonstr = obj.to_json()
        d = json.loads(jsonstr)
        assert d["@class"], "ClassContainingKWOnlyArgs"

    def test_unsafe_hash(self):
        GMC = GoodMSONClass
        a_list = [GMC(1, 1.0, "one"), GMC(2, 2.0, "two")]
        b_dict = {"first": GMC(3, 3.0, "three"), "second": GMC(4, 4.0, "four")}
        c_list_dict_list = [
            {
                "list1": [
                    GMC(5, 5.0, "five"),
                    GMC(6, 6.0, "six"),
                    GMC(7, 7.0, "seven"),
                ],
                "list2": [GMC(8, 8.0, "eight")],
            },
            {
                "list3": [
                    GMC(9, 9.0, "nine"),
                    GMC(10, 10.0, "ten"),
                    GMC(11, 11.0, "eleven"),
                    GMC(12, 12.0, "twelve"),
                ],
                "list4": [GMC(13, 13.0, "thirteen"), GMC(14, 14.0, "fourteen")],
                "list5": [GMC(15, 15.0, "fifteen")],
            },
        ]
        obj = GoodNestedMSONClass(
            a_list=a_list, b_dict=b_dict, c_list_dict_list=c_list_dict_list
        )

        assert (
            a_list[0].unsafe_hash().hexdigest()
            == "ea44de0e2ef627be582282c02c48e94de0d58ec6"
        )
        assert (
            obj.unsafe_hash().hexdigest() == "44204c8da394e878f7562c9aa2e37c2177f28b81"
        )

    def test_version(self):
        obj = self.good_cls("Hello", "World", "Python")
        d = obj.as_dict()
        assert d["@version"] == TESTS_VERSION

    def test_nested_to_from_dict(self):
        GMC = GoodMSONClass
        a_list = [GMC(1, 1.0, "one"), GMC(2, 2.0, "two")]
        b_dict = {"first": GMC(3, 3.0, "three"), "second": GMC(4, 4.0, "four")}
        c_list_dict_list = [
            {
                "list1": [
                    GMC(5, 5.0, "five"),
                    GMC(6, 6.0, "six"),
                    GMC(7, 7.0, "seven"),
                ],
                "list2": [GMC(8, 8.0, "eight")],
            },
            {
                "list3": [
                    GMC(9, 9.0, "nine"),
                    GMC(10, 10.0, "ten"),
                    GMC(11, 11.0, "eleven"),
                    GMC(12, 12.0, "twelve"),
                ],
                "list4": [GMC(13, 13.0, "thirteen"), GMC(14, 14.0, "fourteen")],
                "list5": [GMC(15, 15.0, "fifteen")],
            },
        ]
        obj = GoodNestedMSONClass(
            a_list=a_list, b_dict=b_dict, c_list_dict_list=c_list_dict_list
        )

        obj_dict = obj.as_dict()
        obj2 = GoodNestedMSONClass.from_dict(obj_dict)
        assert [obj2.a_list[ii] == aa for ii, aa in enumerate(obj.a_list)]
        assert [obj2.b_dict[kk] == val for kk, val in obj.b_dict.items()]
        assert len(obj.a_list) == len(obj2.a_list)
        assert len(obj.b_dict) == len(obj2.b_dict)
        s = json.dumps(obj_dict)
        obj3 = json.loads(s, cls=MontyDecoder)
        assert [obj2.a_list[ii] == aa for ii, aa in enumerate(obj3.a_list)]
        assert [obj2.b_dict[kk] == val for kk, val in obj3.b_dict.items()]
        assert len(obj3.a_list) == len(obj2.a_list)
        assert len(obj3.b_dict) == len(obj2.b_dict)
        s = json.dumps(obj, cls=MontyEncoder)
        obj4 = json.loads(s, cls=MontyDecoder)
        assert [obj4.a_list[ii] == aa for ii, aa in enumerate(obj.a_list)]
        assert [obj4.b_dict[kk] == val for kk, val in obj.b_dict.items()]
        assert len(obj.a_list) == len(obj4.a_list)
        assert len(obj.b_dict) == len(obj4.b_dict)

    def test_enum_serialization(self):
        e = EnumTest.a
        d = e.as_dict()
        e_new = EnumTest.from_dict(d)
        assert e_new.name == e.name
        assert e_new.value == e.value

        d = {"123": EnumTest.a}
        f = jsanitize(d)
        assert f["123"]["@module"] == "tests.test_json"
        assert f["123"]["@class"] == "EnumTest"
        assert f["123"]["value"] == 1

        f = jsanitize(d, strict=True)
        assert f["123"]["@module"] == "tests.test_json"
        assert f["123"]["@class"] == "EnumTest"
        assert f["123"]["value"] == 1

        f = jsanitize(d, strict=True, enum_values=True)
        assert f["123"] == 1

        f = jsanitize(d, enum_values=True)
        assert f["123"] == 1

    def test_enum_serialization_no_msonable(self):
        d = {"123": EnumNoAsDict.name_a}
        f = jsanitize(d)
        assert f["123"]["@module"] == "tests.test_json"
        assert f["123"]["@class"] == "EnumNoAsDict"
        assert f["123"]["value"] == "value_a"

        f = jsanitize(d, strict=True)
        assert f["123"]["@module"] == "tests.test_json"
        assert f["123"]["@class"] == "EnumNoAsDict"
        assert f["123"]["value"] == "value_a"

        f = jsanitize(d, strict=True, enum_values=True)
        assert f["123"] == "value_a"

        f = jsanitize(d, enum_values=True)
        assert f["123"] == "value_a"

    def test_save_load(self, tmp_path):
        """Tests the save and load serialization methods."""

        test_good_class = GoodMSONClass(
            "Hello",
            "World",
            "Python",
            **{
                "cant_serialize_me": GoodNOTMSONClass(
                    "Hello2", "World2", "Python2", **{"values": []}
                ),
                "cant_serialize_me2": [
                    GoodNOTMSONClass("Hello4", "World4", "Python4", **{"values": []}),
                    GoodNOTMSONClass("Hello4", "World4", "Python4", **{"values": []}),
                ],
                "cant_serialize_me3": [
                    {
                        "tmp": GoodMSONClass(
                            "Hello5", "World5", "Python5", **{"values": []}
                        ),
                        "tmp2": 2,
                        "tmp3": [1, 2, 3],
                    },
                    {
                        "tmp5": GoodNOTMSONClass(
                            "aHello5", "aWorld5", "aPython5", **{"values": []}
                        ),
                        "tmp2": 5,
                        "tmp3": {"test": "test123"},
                    },
                    # Gotta check that if I hide an MSONable class somewhere
                    # it still gets correctly serialized.
                    {"actually_good": GoodMSONClass("1", "2", "3", **{"values": []})},
                ],
                "values": [],
            },
        )

        # This will pass
        test_good_class.as_dict()

        # This will fail
        with pytest.raises(TypeError):
            test_good_class.to_json()

        # This should also pass though
        target = tmp_path / "test.json"
        test_good_class.save(target, json_kwargs={"indent": 4, "sort_keys": True})

        # This will fail
        with pytest.raises(FileExistsError):
            test_good_class.save(target, strict=True)

        # Now check that reloading this, the classes are equal!
        test_good_class2 = GoodMSONClass.load(target)

        # Final check using load
        test_good_class3 = load(target)

        assert test_good_class == test_good_class2
        assert test_good_class == test_good_class3


class TestJson:
    def test_as_from_dict(self):
        obj = GoodMSONClass(1, 2, 3, hello="world")
        s = json.dumps(obj, cls=MontyEncoder)
        obj2 = json.loads(s, cls=MontyDecoder)
        assert obj2.a == 1
        assert obj2.b == 2
        assert obj2._c == 3
        assert obj2._d == 1
        assert obj2.kwargs, {"hello": "world", "values": []}
        obj = GoodMSONClass(obj, 2, 3)
        s = json.dumps(obj, cls=MontyEncoder)
        obj2 = json.loads(s, cls=MontyDecoder)
        assert obj2.a.a == 1
        assert obj2.b == 2
        assert obj2._c == 3
        assert obj2._d == 1
        listobj = [obj, obj2]
        s = json.dumps(listobj, cls=MontyEncoder)
        listobj2 = json.loads(s, cls=MontyDecoder)
        assert listobj2[0].a.a == 1

    @pytest.mark.skipif(torch is None, reason="torch not present")
    def test_torch_tensor(self):
        # Basic tensor
        t0 = torch.tensor([0, 1, 2])
        t0_json_str = json.dumps(t0, cls=MontyEncoder)
        t0_json_dict = json.loads(t0_json_str)
        t0_from_json = json.loads(t0_json_str, cls=MontyDecoder)

        assert isinstance(t0_from_json, torch.Tensor)
        assert t0_from_json.type() == t0.type()
        assert t0_json_dict["size"] == list(t0.size())
        assert np.array_equal(t0_from_json, t0)

        # Empty tensor
        t_empty = torch.empty((0, 2))
        t_empty_json_str = json.dumps(t_empty, cls=MontyEncoder)
        t_empty_json_dict = json.loads(t_empty_json_str)
        t_empty_from_json = json.loads(t_empty_json_str, cls=MontyDecoder)

        assert isinstance(t_empty_from_json, torch.Tensor)
        assert t_empty_from_json.size() == t_empty.size()
        assert t_empty_json_dict["size"] == list(t_empty.size())
        assert np.array_equal(t_empty_from_json.numpy(), t_empty.numpy())

        # Complex tensor
        ct0 = torch.tensor([1 + 1j, 2 + 1j])
        ct0_json_str = json.dumps(ct0, cls=MontyEncoder)
        ct0_json_dict = json.loads(ct0_json_str)
        ct0_from_json = json.loads(ct0_json_str, cls=MontyDecoder)

        assert isinstance(ct0_from_json, torch.Tensor)
        assert ct0_from_json.type() == ct0.type()
        assert ct0_json_dict["size"] == list(ct0.size())
        assert np.allclose(ct0_from_json.numpy(), ct0.numpy())

        # Empty complex tensor
        ct_empty = torch.empty((0, 2), dtype=torch.complex64)
        ct_empty_json_str = json.dumps(ct_empty, cls=MontyEncoder)
        ct_empty_json_dict = json.loads(ct_empty_json_str)
        ct_empty_from_json = json.loads(ct_empty_json_str, cls=MontyDecoder)

        assert isinstance(ct_empty_from_json, torch.Tensor)
        assert ct_empty_from_json.size() == ct_empty.size()
        assert ct_empty_json_dict["size"] == list(ct_empty.size())
        assert np.array_equal(ct_empty_from_json.numpy(), ct_empty.numpy())

    @pytest.mark.skipif(torch is None, reason="torch not present")
    def test_torch_tensor_backwards_compatibility(self):
        # Simulate an old-style JSON (no "size")
        old_json = json.dumps(
            {
                "@module": "torch",
                "@class": "Tensor",
                "dtype": "torch.LongTensor",
                "data": [0, 1, 2],
            }
        )

        t = json.loads(old_json, cls=MontyDecoder)

        assert isinstance(t, torch.Tensor)
        assert t.dtype == torch.long
        assert t.size() == torch.Size([3])
        assert torch.equal(t, torch.tensor([0, 1, 2]))

        # Test old decoder is compatible with new JSON (with `size`)
        def old_decoder_simulation(json_obj):
            if (
                json_obj.get("@module") == "torch"
                and json_obj.get("@class") == "Tensor"
            ):
                dtype = json_obj["dtype"]
                data = json_obj["data"]
                return torch.tensor(data).type(dtype)
            else:
                raise RuntimeError("")

        # New-style JSON with `size`
        t = torch.empty((0, 2), dtype=torch.float32)
        new_json = json.dumps(t, cls=MontyEncoder)
        json_obj = json.loads(new_json)

        decoded = old_decoder_simulation(json_obj)

        assert isinstance(decoded, torch.Tensor)
        assert list(decoded.size()) == [0] != list(t.size())

    def test_datetime(self):
        dt = datetime.datetime.now()
        jsonstr = json.dumps(dt, cls=MontyEncoder)
        d = json.loads(jsonstr, cls=MontyDecoder)
        assert isinstance(d, datetime.datetime)
        assert dt == d
        # Test a nested datetime.
        a = {"dt": dt, "a": 1}
        jsonstr = json.dumps(a, cls=MontyEncoder)
        d = json.loads(jsonstr, cls=MontyDecoder)
        assert isinstance(d["dt"], datetime.datetime)

        jsanitize(dt, strict=True)

        # test timezone aware datetime API
        created_at = datetime.datetime.now(tz=datetime.timezone.utc)
        data = json.loads(json.dumps(created_at, cls=MontyEncoder))

        created_at_after = MontyDecoder().process_decoded(data)

        assert str(created_at_after).rstrip("0") == str(created_at).rstrip(
            "+00:00"
        ).rstrip("0")

    def test_uuid(self):
        from uuid import UUID, uuid4

        uuid = uuid4()
        jsonstr = json.dumps(uuid, cls=MontyEncoder)
        d = json.loads(jsonstr, cls=MontyDecoder)
        assert isinstance(d, UUID)
        assert uuid == d
        # Test a nested UUID.
        a = {"uuid": uuid, "a": 1}
        jsonstr = json.dumps(a, cls=MontyEncoder)
        d = json.loads(jsonstr, cls=MontyDecoder)
        assert isinstance(d["uuid"], UUID)

    def test_path(self):
        from pathlib import Path

        p = Path("/home/user/")
        jsonstr = json.dumps(p, cls=MontyEncoder)
        d = json.loads(jsonstr, cls=MontyDecoder)
        assert isinstance(d, Path)
        assert d == p

    def test_nan(self):
        x = [float("NaN")]
        djson = json.dumps(x, cls=MontyEncoder)
        d = json.loads(djson)
        assert isinstance(d[0], float)

    def test_numpy(self):
        x = np.array([1, 2, 3], dtype="int64")
        with pytest.raises(TypeError):
            json.dumps(x)
        djson = json.dumps(x, cls=MontyEncoder)
        d = json.loads(djson)
        assert d["@class"] == "array"
        assert d["@module"] == "numpy"
        assert d["data"], [1, 2 == 3]
        assert d["dtype"] == "int64"
        x = json.loads(djson, cls=MontyDecoder)
        assert isinstance(x, np.ndarray)
        x = np.min([1, 2, 3]) > 2
        with pytest.raises(TypeError):
            json.dumps(x)

        x = np.array([1 + 1j, 2 + 1j, 3 + 1j], dtype="complex64")
        with pytest.raises(TypeError):
            json.dumps(x)
        djson = json.dumps(x, cls=MontyEncoder)
        d = json.loads(djson)
        assert d["@class"] == "array"
        assert d["@module"] == "numpy"
        assert d["data"], [[1.0, 2.0, 3.0], [1.0, 1.0 == 1.0]]
        assert d["dtype"] == "complex64"
        x = json.loads(djson, cls=MontyDecoder)
        assert isinstance(x, np.ndarray)
        assert x.dtype == "complex64"

        x = np.array([[1 + 1j, 2 + 1j], [3 + 1j, 4 + 1j]], dtype="complex64")
        with pytest.raises(TypeError):
            json.dumps(x)
        djson = json.dumps(x, cls=MontyEncoder)
        d = json.loads(djson)
        assert d["@class"] == "array"
        assert d["@module"] == "numpy"
        assert d["data"], [[[1.0, 2.0], [3.0, 4.0]], [[1.0, 1.0], [1.0 == 1.0]]]
        assert d["dtype"] == "complex64"
        x = json.loads(djson, cls=MontyDecoder)
        assert isinstance(x, np.ndarray)
        assert x.dtype == "complex64"

        x = {"energies": [np.float64(1234.5)]}
        d = jsanitize(x, strict=True)
        assert isinstance(d["energies"][0], float)

        x = {"energy": np.array(-1.0)}
        d = jsanitize(x, strict=True)
        assert isinstance(d["energy"], float)

        # Test data nested in a class
        x = np.array([[1 + 1j, 2 + 1j], [3 + 1j, 4 + 1j]], dtype="complex64")
        cls = ClassContainingNumpyArray(np_a={"a": [{"b": x}]})

        d = json.loads(json.dumps(cls, cls=MontyEncoder))

        assert d["np_a"]["a"][0]["b"]["@module"] == "numpy"
        assert d["np_a"]["a"][0]["b"]["@class"] == "array"
        assert d["np_a"]["a"][0]["b"]["data"] == [
            [[1.0, 2.0], [3.0, 4.0]],
            [[1.0, 1.0], [1.0, 1.0]],
        ]
        assert d["np_a"]["a"][0]["b"]["dtype"] == "complex64"

        obj = ClassContainingNumpyArray.from_dict(d)
        assert isinstance(obj, ClassContainingNumpyArray)
        assert isinstance(obj.np_a["a"][0]["b"], np.ndarray)
        assert obj.np_a["a"][0]["b"][0][1] == 2 + 1j

    @pytest.mark.skipif(pd is None, reason="pandas not present")
    def test_pandas(self):
        cls = ClassContainingDataFrame(
            df=pd.DataFrame([{"a": 1, "b": 1}, {"a": 1, "b": 2}])
        )

        d = json.loads(MontyEncoder().encode(cls))

        assert d["df"]["@module"] == "pandas"
        assert d["df"]["@class"] == "DataFrame"

        obj = ClassContainingDataFrame.from_dict(d)
        assert isinstance(obj, ClassContainingDataFrame)
        assert isinstance(obj.df, pd.DataFrame)
        assert list(obj.df.a), [1 == 1]

        cls = ClassContainingSeries(s=pd.Series({"a": [1, 2, 3], "b": [4, 5, 6]}))

        d = json.loads(MontyEncoder().encode(cls))

        assert d["s"]["@module"] == "pandas"
        assert d["s"]["@class"] == "Series"

        obj = ClassContainingSeries.from_dict(d)
        assert isinstance(obj, ClassContainingSeries)
        assert isinstance(obj.s, pd.Series)
        assert list(obj.s.a), [1, 2 == 3]

        cls = ClassContainingSeries(
            s={"df": [pd.Series({"a": [1, 2, 3], "b": [4, 5, 6]})]}
        )

        d = json.loads(MontyEncoder().encode(cls))

        assert d["s"]["df"][0]["@module"] == "pandas"
        assert d["s"]["df"][0]["@class"] == "Series"

        obj = ClassContainingSeries.from_dict(d)
        assert isinstance(obj, ClassContainingSeries)
        assert isinstance(obj.s["df"][0], pd.Series)
        assert list(obj.s["df"][0].a), [1, 2 == 3]

    @pytest.mark.skipif(pint is None, reason="pint not present")
    def test_pint_quantity(self):
        ureg = pint.UnitRegistry()
        cls = ClassContainingQuantity(qty=pint.Quantity("9.81 m/s**2"))

        d = json.loads(MontyEncoder().encode(cls))
        assert isinstance(d, dict)

        assert d["qty"]["@module"] == "pint"
        assert d["qty"]["@class"] == "Quantity"
        assert d["qty"].get("@version") is not None

        obj = ClassContainingQuantity.from_dict(d)
        assert isinstance(obj, ClassContainingQuantity)
        assert isinstance(obj.qty, pint.Quantity)
        assert obj.qty.magnitude == 9.81
        assert str(obj.qty.units) == "meter / second ** 2"

    def test_callable(self):
        instance = MethodSerializationClass(a=1)
        for function in [
            # builtins
            str,
            list,
            sum,
            open,
            # functions
            os.path.join,
            my_callable,
            # unbound methods
            MethodSerializationClass.NestedClass.inner_method,
            MethodSerializationClass.staticmethod,
            instance.staticmethod,
            # methods bound to classes
            MethodSerializationClass.classmethod,
            instance.classmethod,
            # classes
            MethodSerializationClass,
            Enum,
        ]:
            with pytest.raises(TypeError):
                json.dumps(function)
            djson = json.dumps(function, cls=MontyEncoder)
            d = json.loads(djson)
            assert "@callable" in d
            assert "@module" in d
            x = json.loads(djson, cls=MontyDecoder)
            assert x == function

        # test method bound to instance
        for function in [instance.method]:
            with pytest.raises(TypeError):
                json.dumps(function)
            djson = json.dumps(function, cls=MontyEncoder)
            d = json.loads(djson)
            assert "@callable" in d
            assert "@module" in d
            x = json.loads(djson, cls=MontyDecoder)

            # can't just check functions are equal as the instance the function is bound
            # to will be different. Instead, we check that the serialized instance
            # is the same, and that the function qualname is the same
            assert x.__qualname__ == function.__qualname__
            assert x.__self__.as_dict() == function.__self__.as_dict()

        # test method bound to object that is not serializable
        for function in [MethodNonSerializationClass(1).method]:
            with pytest.raises(TypeError):
                json.dumps(function, cls=MontyEncoder)

        # test that callable MSONable objects still get serialized as the objects
        # rather than as a callable
        djson = json.dumps(instance, cls=MontyEncoder)
        assert "@class" in djson

    @pytest.mark.skipif(ObjectId is None, reason="bson not present")
    def test_objectid(self):
        oid = ObjectId("562e8301218dcbbc3d7d91ce")
        with pytest.raises(TypeError):
            json.dumps(oid)
        djson = json.dumps(oid, cls=MontyEncoder)
        x = json.loads(djson, cls=MontyDecoder)
        assert isinstance(x, ObjectId)

    def test_jsanitize(self):
        # clean_json should have no effect on None types.
        d = {"hello": 1, "world": None}
        clean = jsanitize(d)
        assert clean["world"] is None
        assert json.loads(json.dumps(d)) == json.loads(json.dumps(clean))

        d = {"hello": GoodMSONClass(1, 2, 3), "test": "hi"}
        with pytest.raises(TypeError):
            json.dumps(d)
        clean = jsanitize(d)
        assert isinstance(clean["hello"], str)
        clean_strict = jsanitize(d, strict=True)
        assert clean_strict["hello"]["a"] == 1
        assert clean_strict["hello"]["b"] == 2
        assert clean_strict["test"] == "hi"
        clean_recursive_msonable = jsanitize(d, recursive_msonable=True)
        assert clean_recursive_msonable["hello"]["a"] == 1
        assert clean_recursive_msonable["hello"]["b"] == 2
        assert clean_recursive_msonable["hello"]["c"] == 3
        assert clean_recursive_msonable["test"] == "hi"

        d = {"hello": [GoodMSONClass(1, 2, 3), "test"], "test": "hi"}
        clean_recursive_msonable = jsanitize(d, recursive_msonable=True)
        assert clean_recursive_msonable["hello"][0]["a"] == 1
        assert clean_recursive_msonable["hello"][0]["b"] == 2
        assert clean_recursive_msonable["hello"][0]["c"] == 3
        assert clean_recursive_msonable["hello"][1] == "test"
        assert clean_recursive_msonable["test"] == "hi"

        d = {"hello": (GoodMSONClass(1, 2, 3), "test"), "test": "hi"}
        clean_recursive_msonable = jsanitize(d, recursive_msonable=True)
        assert clean_recursive_msonable["hello"][0]["a"] == 1
        assert clean_recursive_msonable["hello"][0]["b"] == 2
        assert clean_recursive_msonable["hello"][0]["c"] == 3
        assert clean_recursive_msonable["hello"][1] == "test"
        assert clean_recursive_msonable["test"] == "hi"

        DoubleGoodMSONClass = GoodMSONClass(1, 2, 3)
        DoubleGoodMSONClass.values = [GoodMSONClass(1, 2, 3)]
        clean_recursive_msonable = jsanitize(
            DoubleGoodMSONClass, recursive_msonable=True
        )
        assert clean_recursive_msonable["a"] == 1
        assert clean_recursive_msonable["b"] == 2
        assert clean_recursive_msonable["c"] == 3
        assert clean_recursive_msonable["values"][0]["a"] == 1
        assert clean_recursive_msonable["values"][0]["b"] == 2
        assert clean_recursive_msonable["values"][0]["c"] == 3

        d = {"dt": datetime.datetime.now()}
        clean = jsanitize(d)
        assert isinstance(clean["dt"], str)
        clean = jsanitize(d, allow_bson=True)
        assert isinstance(clean["dt"], datetime.datetime)

        rnd_bin = bytes(np.random.rand(10))
        d = {"a": bytes(rnd_bin)}
        clean = jsanitize(d, allow_bson=True)
        assert clean["a"] == bytes(rnd_bin)
        assert isinstance(clean["a"], bytes)

        p = pathlib.Path("/home/user/")
        clean = jsanitize(p, strict=True)
        assert clean, ["/home/user" in "\\home\\user"]

        # test jsanitizing callables (including classes)
        instance = MethodSerializationClass(a=1)
        for function in [
            # builtins
            str,
            list,
            sum,
            open,
            # functions
            os.path.join,
            my_callable,
            # unbound methods
            MethodSerializationClass.NestedClass.inner_method,
            MethodSerializationClass.staticmethod,
            instance.staticmethod,
            # methods bound to classes
            MethodSerializationClass.classmethod,
            instance.classmethod,
            # classes
            MethodSerializationClass,
            Enum,
        ]:
            d = {"f": function}
            clean = jsanitize(d)
            assert "@module" in clean["f"]
            assert "@callable" in clean["f"]

        # test method bound to instance
        for function in [instance.method]:
            d = {"f": function}
            clean = jsanitize(d)
            assert "@module" in clean["f"]
            assert "@callable" in clean["f"]
            assert clean["f"].get("@bound", None) is not None
            assert "@class" in clean["f"]["@bound"]

        # test method bound to object that is not serializable
        for function in [MethodNonSerializationClass(1).method]:
            d = {"f": function}
            clean = jsanitize(d)
            assert isinstance(clean["f"], str)

            # test that strict checking gives an error
            with pytest.raises(AttributeError):
                jsanitize(d, strict=True)

        # test that callable MSONable objects still get serialized as the objects
        # rather than as a callable
        d = {"c": instance}
        clean = jsanitize(d, strict=True)
        assert "@class" in clean["c"]

    def test_unserializable_composite(self):
        class Unserializable:
            def __init__(self, a):
                self._a = a

            def __str__(self):
                return "Unserializable"

        class Composite(MSONable):
            def __init__(self, name, unserializable, msonable):
                self.name = name
                self.unserializable = unserializable
                self.msonable = msonable

        composite_dictionary = {
            "name": "test",
            "unserializable": Unserializable(1),
            "msonable": GoodMSONClass(1, 2, 3),
        }

        with pytest.raises(AttributeError):
            jsanitize(composite_dictionary, strict=True)

        composite_obj = Composite.from_dict(composite_dictionary)

        with pytest.raises(AttributeError):
            jsanitize(composite_obj, strict=True)

        # Test that skip mode preserves unserializable objects
        skipped_dict = jsanitize(composite_obj, strict="skip", recursive_msonable=True)
        assert skipped_dict["name"] == "test", "String values should remain unchanged"
        assert skipped_dict["unserializable"]._a == 1, (
            "Unserializable object should be preserved in skip mode"
        )
        assert skipped_dict["msonable"]["a"] == 1, (
            "MSONable object should be properly serialized"
        )

        # Test non-strict mode converts unserializable to string
        dict_with_str = jsanitize(composite_obj, strict=False, recursive_msonable=True)
        assert isinstance(dict_with_str["unserializable"], str), (
            "Unserializable object should be converted to string in non-strict mode"
        )

    @pytest.mark.skipif(pd is None, reason="pandas not present")
    def test_jsanitize_pandas(self):
        s = pd.Series({"a": [1, 2, 3], "b": [4, 5, 6]})
        clean = jsanitize(s)
        assert clean == s.to_dict()

    @pytest.mark.skipif(ObjectId is None, reason="bson not present")
    def test_jsanitize_numpy_bson(self):
        d = {
            "a": ["b", np.array([1, 2, 3])],
            "b": ObjectId.from_datetime(datetime.datetime.now()),
        }
        clean = jsanitize(d)
        assert clean["a"], ["b", [1, 2 == 3]]
        assert isinstance(clean["b"], str)

    def test_redirect(self):
        MSONable.REDIRECT["tests.test_json"] = {
            "test_class": {"@class": "GoodMSONClass", "@module": "tests.test_json"},
            "another_test_class": {
                "@class": "AnotherClass",
                "@module": "tests.test_json2",
            },
        }

        d = {
            "@class": "test_class",
            "@module": "tests.test_json",
            "a": 1,
            "b": 1,
            "c": 1,
        }

        obj = json.loads(json.dumps(d), cls=MontyDecoder)
        assert isinstance(obj, GoodMSONClass)

        d2 = {
            "@class": "another_test_class",
            "@module": "tests.test_json",
            "a": 2,
            "b": 2,
            "c": 2,
        }

        with pytest.raises(ImportError, match="No module named 'tests.test_json2'"):
            # This should raise ImportError because it's trying to load
            # AnotherClass from tests.test_json instead of tests.test_json2
            json.loads(json.dumps(d2), cls=MontyDecoder)

    def test_redirect_settings_file(self):
        data = _load_redirect(os.path.join(TEST_DIR, "settings_for_test.yaml"))
        assert data == {
            "old_module": {
                "old_class": {"@class": "new_class", "@module": "new_module"}
            }
        }

    @pytest.mark.skipif(pydantic is None, reason="pydantic not present")
    def test_pydantic_integrations(self):
        from pydantic import BaseModel, ValidationError

        global ModelWithMSONable  # allow model to be deserialized in test
        global LimitedMSONClass

        class ModelWithMSONable(BaseModel):
            a: GoodMSONClass

        test_object = ModelWithMSONable(a=GoodMSONClass(1, 1, 1))
        test_dict_object = ModelWithMSONable(a=test_object.a.as_dict())
        assert test_dict_object.a.a == test_object.a.a
        dict_no_class = test_object.a.as_dict()
        dict_no_class.pop("@class")
        dict_no_class.pop("@module")
        test_dict_object = ModelWithMSONable(a=dict_no_class)
        assert test_dict_object.a.a == test_object.a.a

        assert test_object.model_json_schema() == {
            "title": "ModelWithMSONable",
            "type": "object",
            "properties": {
                "a": {
                    "title": "A",
                    "type": "object",
                    "properties": {
                        "@class": {"enum": ["GoodMSONClass"], "type": "string"},
                        "@module": {"enum": ["tests.test_json"], "type": "string"},
                        "@version": {"type": "string"},
                    },
                    "required": ["@class", "@module"],
                }
            },
            "required": ["a"],
        }

        d = jsanitize(test_object, strict=True, enum_values=True, allow_bson=True)
        assert d == {
            "a": {
                "@module": "tests.test_json",
                "@class": "GoodMSONClass",
                "@version": "0.1",
                "a": 1,
                "b": 1,
                "c": 1,
                "d": 1,
                "values": [],
            },
            "@module": "tests.test_json",
            "@class": "ModelWithMSONable",
            "@version": "0.1",
        }
        obj = MontyDecoder().process_decoded(d)
        assert isinstance(obj, BaseModel)
        assert isinstance(obj.a, GoodMSONClass)
        assert obj.a.b == 1

        # check that a model that is not validated by pydantic still
        # gets completely deserialized.
        global ModelWithDict  # allow model to be deserialized in test

        class ModelWithDict(BaseModel):
            a: dict

        test_object_with_dict = ModelWithDict(a={"x": GoodMSONClass(1, 1, 1)})
        d = jsanitize(
            test_object_with_dict, strict=True, enum_values=True, allow_bson=True
        )
        assert d == {
            "a": {
                "x": {
                    "@module": "tests.test_json",
                    "@class": "GoodMSONClass",
                    "@version": "0.1",
                    "a": 1,
                    "b": 1,
                    "c": 1,
                    "d": 1,
                    "values": [],
                }
            },
            "@module": "tests.test_json",
            "@class": "ModelWithDict",
            "@version": "0.1",
        }
        obj = MontyDecoder().process_decoded(d)
        assert isinstance(obj, BaseModel)
        assert isinstance(obj.a["x"], GoodMSONClass)
        assert obj.a["x"].b == 1

        # check that if an MSONable object raises an exception during
        # the model validation it is properly handled by pydantic
        global ModelWithUnion  # allow model to be deserialized in test
        global ModelWithLimited  # allow model to be deserialized in test

        class ModelWithLimited(BaseModel):
            a: LimitedMSONClass

        class ModelWithUnion(BaseModel):
            a: Union[LimitedMSONClass, dict]

        limited_dict = jsanitize(ModelWithLimited(a=LimitedMSONClass(1)), strict=True)
        assert ModelWithLimited.model_validate(limited_dict)
        limited_dict["a"]["b"] = 2
        with pytest.raises(ValidationError):
            ModelWithLimited.model_validate(limited_dict)

        limited_union_dict = jsanitize(
            ModelWithUnion(a=LimitedMSONClass(1)), strict=True
        )
        validated_model = ModelWithUnion.model_validate(limited_union_dict)
        assert isinstance(validated_model, ModelWithUnion)
        assert isinstance(validated_model.a, LimitedMSONClass)
        limited_union_dict["a"]["b"] = 2
        validated_model = ModelWithUnion.model_validate(limited_union_dict)
        assert isinstance(validated_model, ModelWithUnion)
        assert isinstance(validated_model.a, dict)

    def test_dataclass(self):
        c = Coordinates([Point(1, 2), Point(3, 4)])
        d = c.as_dict()
        c2 = Coordinates.from_dict(d)
        assert d["points"][0]["x"] == 1
        assert d["points"][1]["y"] == 4
        assert isinstance(c2, Coordinates)
        assert isinstance(c2.points[0], Point)

        s = MontyEncoder().encode(Point(1, 2))
        p = MontyDecoder().decode(s)
        assert p.x == 1
        assert p.y == 2

        ndc = NestedDataClass([Point(1, 2), Point(3, 4)])
        str_ = json.dumps(ndc, cls=MontyEncoder)
        ndc2 = json.loads(str_, cls=MontyDecoder)
        assert isinstance(ndc2, NestedDataClass)

    def test_enum(self):
        s = MontyEncoder().encode(EnumNoAsDict.name_a)
        p = MontyDecoder().decode(s)
        assert p.name == "name_a"
        assert p.value == "value_a"

        na1 = EnumAsDict.name_a
        d_ = na1.as_dict()
        assert d_ == {"v": "value_a"}
        na2 = EnumAsDict.from_dict(d_)
        assert na2 == na1

    def test_partial_serializable(self, tmp_path):
        is_m = GoodMSONClass(a=1, b=2, c=3)
        not_m = GoodNOTMSONClass(a="a", b="b", c="c")

        is_m_jsons, is_m_map = partial_monty_encode(is_m)
        is_m_d = json.loads(is_m_jsons)
        assert is_m_d["@class"] == "GoodMSONClass"
        assert is_m_d["a"] == 1
        assert len(is_m_map) == 0

        not_m_jsons, not_m_map = partial_monty_encode(not_m)
        not_m_d = json.loads(not_m_jsons)
        assert not_m_d["@class"] == "GoodNOTMSONClass"
        assert "@object_reference" in not_m_d
        assert len(not_m_map) == 1
        mixed = {"is_m": is_m, "not_m": not_m}
        mixed_jsons, mixed_map = partial_monty_encode(mixed, {"indent": 2})
        mixed_d = json.loads(mixed_jsons)
        assert mixed_d["is_m"]["a"] == 1
        assert mixed_d["is_m"]["@class"] == "GoodMSONClass"
        assert "@object_reference" in mixed_d["not_m"]
        assert mixed_d["not_m"]["@class"] == "GoodNOTMSONClass"

        mixed = {"is_m": is_m, "not_m": not_m}
        save(mixed, tmp_path / "mixed.json")
        loaded = load2dict(tmp_path / "mixed.json")
        assert loaded["is_m"]["a"] == 1
        assert loaded["not_m"].a == "a"

        # Test when you are allowed to overwrite
        with pytest.raises(FileExistsError):
            save(mixed, tmp_path / "mixed.json")

        save(mixed, tmp_path / "mixed.json", strict=False)


class TestCheckType:
    def test_check_subclass(self):
        class A:
            pass

        class B(A):
            pass

        a, b = A(), B()

        class_name_A = f"{type(a).__module__}.{type(a).__qualname__}"
        class_name_B = f"{type(b).__module__}.{type(b).__qualname__}"

        # a is an instance of A, but not B
        assert _check_type(a, class_name_A)
        assert isinstance(a, A)
        assert not _check_type(a, class_name_B)
        assert not isinstance(a, B)

        # b is an instance of both B and A
        assert _check_type(b, class_name_B)
        assert isinstance(b, B)
        assert _check_type(b, class_name_A)
        assert isinstance(b, A)

    def test_check_class(self):
        """This should not work for classes."""

        class A:
            pass

        class B(A):
            pass

        class_name_A = f"{A.__module__}.{A.__qualname__}"
        class_name_B = f"{B.__module__}.{B.__qualname__}"

        # Test class behavior (should return False, like isinstance does)
        assert not _check_type(A, class_name_A)
        assert not _check_type(B, class_name_B)
        assert not _check_type(B, class_name_A)

    def test_callable(self):
        # Test function
        def my_function():
            pass

        callable_class_name = (
            f"{type(my_function).__module__}.{type(my_function).__qualname__}"
        )

        assert _check_type(my_function, callable_class_name), callable_class_name
        assert isinstance(my_function, type(my_function))

        # Test callable class
        class MyCallableClass:
            def __call__(self):
                pass

        callable_instance = MyCallableClass()
        assert callable(callable_instance)

        callable_class_instance_name = f"{type(callable_instance).__module__}.{type(callable_instance).__qualname__}"

        assert _check_type(callable_instance, callable_class_instance_name), (
            callable_class_instance_name
        )
        assert isinstance(callable_instance, MyCallableClass)

    def test_numpy(self):
        # Test NumPy array
        arr = np.array([1, 2, 3])

        assert _check_type(arr, "numpy.ndarray")
        assert isinstance(arr, np.ndarray)

        # Test NumPy generic
        scalar = np.float64(3.14)

        assert _check_type(scalar, "numpy.generic")
        assert isinstance(scalar, np.generic)

    @pytest.mark.skipif(pd is None, reason="pandas is not installed")
    def test_pandas(self):
        # Test pandas DataFrame
        df = pd.DataFrame({"a": [1, 2, 3]})

        assert _check_type(df, "pandas.core.frame.DataFrame")
        assert isinstance(df, pd.DataFrame)

        assert _check_type(df, "pandas.core.base.PandasObject")
        assert isinstance(df, pd.core.base.PandasObject)

        # Test pandas Series
        series = pd.Series([1, 2, 3])

        assert _check_type(series, "pandas.core.series.Series")
        assert isinstance(series, pd.Series)

        assert _check_type(series, "pandas.core.base.PandasObject")
        assert isinstance(series, pd.core.base.PandasObject)

    @pytest.mark.skipif(torch is None, reason="torch is not installed")
    def test_torch(self):
        tensor = torch.tensor([1, 2, 3])

        assert _check_type(tensor, "torch.Tensor")
        assert isinstance(tensor, torch.Tensor)

    @pytest.mark.skipif(pydantic is None, reason="pydantic is not installed")
    def test_pydantic(self):
        class MyModel(pydantic.BaseModel):
            name: str

        model_instance = MyModel(name="Alice")

        assert _check_type(model_instance, "pydantic.main.BaseModel")
        assert isinstance(model_instance, pydantic.BaseModel)

    @pytest.mark.skipif(pint is None, reason="pint is not installed")
    def test_pint(self):
        ureg = pint.UnitRegistry()
        qty = 3 * ureg.meter

        assert _check_type(qty, "pint.registry.Quantity")
        assert isinstance(qty, pint.Quantity)

    @pytest.mark.skipif(ObjectId is None, reason="bson not present")
    @pytest.mark.skipif(json_util is None, reason="pymongo not present")
    def test_extended_json(self):
        ext_json_dict = {
            "datetime": datetime.datetime.now(datetime.timezone.utc),
            "NaN": float("NaN"),
            "infinity": float("inf"),
            "-infinity": -float("inf"),
        }
        ext_json_str = json_util.dumps(ext_json_dict)

        not_serialized = json.loads(ext_json_str)
        assert all(isinstance(v, dict) for v in not_serialized.values())

        reserialized = MontyDecoder().decode(ext_json_str)
        for k, v in ext_json_dict.items():
            if k == "datetime":
                # BSON's json_util only saves datetimes up to microseconds
                assert reserialized[k].timestamp() == pytest.approx(
                    v.timestamp(), abs=1e-3
                )
            elif k == "NaN":
                assert np.isnan(reserialized[k])
            else:
                assert v == reserialized[k]
            assert not isinstance(reserialized[k], dict)
