from __future__ import annotations

import gc
import pickle
import weakref
from typing import TYPE_CHECKING

import pytest

from monty.design_patterns import cached_class, singleton

if TYPE_CHECKING:
    from typing import Any


class TestSingleton:
    def test_singleton(self):
        @singleton
        class A:
            pass

        a1 = A()
        a2 = A()

        assert id(a1) == id(a2)


@cached_class
class A:
    def __init__(self, val):
        self.val = val

    def __eq__(self, other):
        return self.val == other.val

    def __getinitargs__(self):
        return (self.val,)

    def __getnewargs__(self):
        return (self.val,)


class TestCachedClass:
    def test_cached_class(self):
        a1a = A(1)
        a1b = A(1)
        a2 = A(2)

        assert id(a1a) == id(a1b)
        assert id(a1a) != id(a2)

    def test_pickle(self):
        a = A(2)
        o = pickle.dumps(a)
        assert a == pickle.loads(o)


@cached_class
class ClassForTest:
    def __init__(self, value: Any) -> None:
        self.value = value


def test_caching():
    # Test that instances are cached
    inst1 = ClassForTest(1)
    inst2 = ClassForTest(1)
    assert inst1 is inst2

    inst3 = ClassForTest(2)
    assert inst1 is not inst3


def test_picklability():
    # Test that instances can be pickled and unpickled
    original = ClassForTest(42)
    pickled = pickle.dumps(original)
    unpickled = pickle.loads(pickled)

    # Check that the unpickled instance has the same value
    assert original.value == unpickled.value

    # Check that the unpickled instance is the same as a newly created instance
    new_instance = ClassForTest(42)
    assert unpickled is new_instance


def test_initialization():
    init_count = 0

    @cached_class
    class TestInitClass:
        def __init__(self):
            nonlocal init_count
            init_count += 1

    inst1 = TestInitClass()
    inst2 = TestInitClass()
    assert init_count == 1


def test_class_identity():
    # Ensure the decorated class is still recognized as the original class
    assert isinstance(ClassForTest(1), ClassForTest)
    assert type(ClassForTest(1)) is ClassForTest


def test_multiple_arguments():
    @cached_class
    class MultiArgClass:
        def __init__(self, a, b, c=3):
            self.args = (a, b, c)

    inst1 = MultiArgClass(1, 2)
    inst2 = MultiArgClass(1, 2)
    inst3 = MultiArgClass(1, 2, 4)

    assert inst1 is inst2
    assert inst1 is not inst3
    assert inst1.args == (1, 2, 3)
    assert inst3.args == (1, 2, 4)


def test_different_argument_types():
    @cached_class
    class MultiTypeClass:
        def __init__(self, a, b, c):
            self.a, self.b, self.c = a, b, c

    inst1 = MultiTypeClass(1, "string", (1, 2))
    inst2 = MultiTypeClass(1, "string", (1, 2))
    assert inst1 is inst2

    inst3 = MultiTypeClass(1, "string", [1, 2])  # Unhashable argument
    assert inst1 is not inst3


def test_keyword_arguments():
    @cached_class
    class KeywordClass:
        def __init__(self, a, b, c=3):
            self.a, self.b, self.c = a, b, c

    inst1 = KeywordClass(1, 2)
    inst2 = KeywordClass(a=1, b=2)
    assert inst1 is inst2

    inst3 = KeywordClass(1, 2, 4)
    assert inst1 is not inst3


def test_inheritance_chain():
    @cached_class
    class GrandParent:
        def __init__(self, value):
            self.value = value

    class Parent(GrandParent):
        pass

    @cached_class
    class Child(Parent):
        pass

    gp1 = GrandParent(1)
    gp2 = GrandParent(1)
    assert gp1 is gp2

    p1 = Parent(1)
    p2 = Parent(1)
    assert p1 is p2
    assert p1 is not gp1

    c1 = Child(1)
    c2 = Child(1)
    assert c1 is c2
    assert c1 is not p1


def test_memory_management():
    @cached_class
    class WeakRefClass:
        def __init__(self, value):
            self.value = value

    inst = WeakRefClass(1)
    weak_ref = weakref.ref(inst)

    del inst
    gc.collect()

    assert weak_ref() is None

    # Creating a new instance should work
    new_inst = WeakRefClass(1)
    assert new_inst.value == 1


def test_exception_in_init():
    init_count = 0

    @cached_class
    class ExceptionClass:
        def __init__(self, value):
            nonlocal init_count
            init_count += 1
            if init_count == 1:
                raise ValueError("First init failed")
            self.value = value

    with pytest.raises(ValueError):
        ExceptionClass(1)

    assert init_count == 1

    # Second attempt should work and use cache
    inst1 = ExceptionClass(1)
    inst2 = ExceptionClass(1)
    assert inst1 is inst2
    assert init_count == 2


def test_property_and_method_behavior():
    @cached_class
    class PropertyClass:
        def __init__(self, value):
            self._value = value

        @property
        def value(self):
            return self._value

        def get_value(self):
            return self._value

    inst1 = PropertyClass(1)
    inst2 = PropertyClass(1)

    assert inst1 is inst2
    assert inst1.value == 1
    assert inst1.get_value() == 1


def test_class_method_and_static_method():
    @cached_class
    class MethodClass:
        def __init__(self, value):
            self.value = value

        @classmethod
        def create(cls, value):
            return cls(value)

        @staticmethod
        def static_method(value):
            return value * 2

    inst1 = MethodClass(1)
    inst2 = MethodClass.create(1)
    assert inst1 is inst2

    assert MethodClass.static_method(5) == 10


def test_nested_cached_classes():
    @cached_class
    class OuterClass:
        def __init__(self, value):
            self.value = value

        @cached_class
        class InnerClass:
            def __init__(self, inner_value):
                self.inner_value = inner_value

    outer1 = OuterClass(1)
    outer2 = OuterClass(1)
    assert outer1 is outer2

    inner1 = outer1.InnerClass(2)
    inner2 = outer2.InnerClass(2)
    assert inner1 is inner2


def test_large_number_of_instances():
    @cached_class
    class LargeNumberClass:
        def __init__(self, value):
            self.value = value

    instances = [LargeNumberClass(i) for i in range(1000)]
    for i, inst in enumerate(instances):
        assert inst is LargeNumberClass(i)
