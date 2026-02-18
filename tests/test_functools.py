from __future__ import annotations

import platform
import time

import pytest

from monty.functools import (
    TimeoutError,
    lazy_property,
    prof_main,
    return_if_raise,
    return_none_if_raise,
    timeout,
)


class TestLazy:
    def test_evaluate(self):
        # Lazy attributes should be evaluated when accessed.
        called = []

        class Foo:
            @lazy_property
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        assert f.foo == 1
        assert len(called) == 1

    def test_evaluate_once(self):
        # lazy_property attributes should be evaluated only once.
        called = []

        class Foo:
            @lazy_property
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        assert f.foo == 1
        assert f.foo == 1
        assert f.foo == 1
        assert len(called) == 1

    def test_private_attribute(self):
        # It should be possible to create private, name-mangled
        # lazy_property attributes.
        called = []

        class Foo:
            @lazy_property
            def __foo(self):
                called.append("foo")
                return 1

            def get_foo(self):
                return self.__foo

        f = Foo()
        assert f.get_foo() == 1
        assert f.get_foo() == 1
        assert f.get_foo() == 1
        assert len(called) == 1

    def test_reserved_attribute(self):
        # It should be possible to create reserved lazy_property attributes.
        called = []

        class Foo:
            @lazy_property
            def __foo__(self):
                called.append("foo")
                return 1

        f = Foo()
        assert f.__foo__ == 1
        assert f.__foo__ == 1
        assert f.__foo__ == 1
        assert len(called) == 1

    def test_result_shadows_descriptor(self):
        # The result of the function call should be stored in
        # the object __dict__, shadowing the descriptor.
        called = []

        class Foo:
            @lazy_property
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        assert isinstance(Foo.foo, lazy_property)
        assert f.foo is f.foo
        assert f.foo is f.__dict__["foo"]  # !
        assert len(called) == 1

        assert f.foo == 1
        assert f.foo == 1
        assert len(called) == 1

        lazy_property.invalidate(f, "foo")

        assert f.foo == 1
        assert len(called) == 2

        assert f.foo == 1
        assert f.foo == 1
        assert len(called) == 2

    def test_readonly_object(self):
        # The descriptor should raise an AttributeError when lazy_property is
        # used on a read-only object (an object with __slots__).
        called = []

        class Foo:
            __slots__ = ()

            @lazy_property
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        assert len(called) == 0

        with pytest.raises(
            AttributeError, match="'Foo' object has no attribute '__dict__'"
        ):
            f.foo

        # The function was not called
        assert len(called) == 0

    def test_introspection(self):
        # The lazy_property decorator should support basic introspection.

        class Foo:
            def foo(self):
                """foo func doc"""

            @lazy_property
            def bar(self):
                """bar func doc"""

        assert Foo.foo.__name__ == "foo"
        assert Foo.foo.__doc__ == "foo func doc"
        assert "test_functools" in Foo.foo.__module__

        assert Foo.bar.__name__ == "bar"
        assert Foo.bar.__doc__ == "bar func doc"
        assert "test_functools" in Foo.bar.__module__


class TestInvalidate:
    def test_invalidate_attribute(self):
        # It should be possible to invalidate a lazy_property attribute.
        called = []

        class Foo:
            @lazy_property
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        assert f.foo == 1
        assert len(called) == 1

        lazy_property.invalidate(f, "foo")

        assert f.foo == 1
        assert len(called) == 2

    def test_invalidate_attribute_twice(self):
        # It should be possible to invalidate a lazy_property attribute
        # twice without causing harm.
        called = []

        class Foo:
            @lazy_property
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        assert f.foo == 1
        assert len(called) == 1

        lazy_property.invalidate(f, "foo")
        lazy_property.invalidate(f, "foo")  # Nothing happens

        assert f.foo == 1
        assert len(called) == 2

    def test_invalidate_uncalled_attribute(self):
        # It should be possible to invalidate an empty attribute
        # cache without causing harm.
        called = []

        class Foo:
            @lazy_property
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        assert len(called) == 0
        lazy_property.invalidate(f, "foo")  # Nothing happens

    def test_invalidate_private_attribute(self):
        # It should be possible to invalidate a private lazy_property attribute.
        called = []

        class Foo:
            @lazy_property
            def __foo(self):
                called.append("foo")
                return 1

            def get_foo(self):
                return self.__foo

        f = Foo()
        assert f.get_foo() == 1
        assert len(called) == 1

        lazy_property.invalidate(f, "__foo")

        assert f.get_foo() == 1
        assert len(called) == 2

    def test_invalidate_mangled_attribute(self):
        # It should be possible to invalidate a private lazy_property attribute
        # by its mangled name.
        called = []

        class Foo:
            @lazy_property
            def __foo(self):
                called.append("foo")
                return 1

            def get_foo(self):
                return self.__foo

        f = Foo()
        assert f.get_foo() == 1
        assert len(called) == 1

        lazy_property.invalidate(f, "_Foo__foo")

        assert f.get_foo() == 1
        assert len(called) == 2

    def test_invalidate_reserved_attribute(self):
        # It should be possible to invalidate a reserved lazy_property attribute.
        called = []

        class Foo:
            @lazy_property
            def __foo__(self):
                called.append("foo")
                return 1

        f = Foo()
        assert f.__foo__ == 1
        assert len(called) == 1

        lazy_property.invalidate(f, "__foo__")

        assert f.__foo__ == 1
        assert len(called) == 2

    def test_invalidate_nonlazy_attribute(self):
        # Invalidating an attribute that is not lazy_property should
        # raise an AttributeError.
        called = []

        class Foo:
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        with pytest.raises(
            AttributeError, match="'Foo.foo' is not a lazy_property attribute"
        ):
            lazy_property.invalidate(f, "foo")

    def test_invalidate_nonlazy_private_attribute(self):
        # Invalidating a private attribute that is not lazy_property should
        # raise an AttributeError.
        called = []

        class Foo:
            def __foo(self):
                called.append("foo")
                return 1

        f = Foo()
        with pytest.raises(
            AttributeError, match="type object 'Foo' has no attribute 'foo'"
        ):
            lazy_property.invalidate(f, "foo")

    def test_invalidate_unknown_attribute(self):
        # Invalidating an unknown attribute should
        # raise an AttributeError.
        called = []

        class Foo:
            @lazy_property
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        with pytest.raises(
            AttributeError, match="type object 'Foo' has no attribute 'bar'"
        ):
            lazy_property.invalidate(f, "bar")

    def test_invalidate_readonly_object(self):
        # Calling invalidate on a read-only object should
        # raise an AttributeError.
        called = []

        class Foo:
            __slots__ = ()

            @lazy_property
            def foo(self):
                called.append("foo")
                return 1

        f = Foo()
        with pytest.raises(
            AttributeError, match="'Foo' object has no attribute '__dict__'"
        ):
            lazy_property.invalidate(f, "foo")


# A lazy_property subclass
class cached(lazy_property):
    pass


class TestInvalidateSubclass:
    def test_invalidate_attribute(self):
        # It should be possible to invalidate a cached attribute.
        called = []

        class Bar:
            @cached
            def bar(self):
                called.append("bar")
                return 1

        b = Bar()
        assert b.bar == 1
        assert len(called) == 1

        cached.invalidate(b, "bar")

        assert b.bar == 1
        assert len(called) == 2

    def test_invalidate_attribute_twice(self):
        # It should be possible to invalidate a cached attribute
        # twice without causing harm.
        called = []

        class Bar:
            @cached
            def bar(self):
                called.append("bar")
                return 1

        b = Bar()
        assert b.bar == 1
        assert len(called) == 1

        cached.invalidate(b, "bar")
        cached.invalidate(b, "bar")  # Nothing happens

        assert b.bar == 1
        assert len(called) == 2

    def test_invalidate_uncalled_attribute(self):
        # It should be possible to invalidate an empty attribute
        # cache without causing harm.
        called = []

        class Bar:
            @cached
            def bar(self):
                called.append("bar")
                return 1

        b = Bar()
        assert len(called) == 0
        cached.invalidate(b, "bar")  # Nothing happens

    def test_invalidate_private_attribute(self):
        # It should be possible to invalidate a private cached attribute.
        called = []

        class Bar:
            @cached
            def __bar(self):
                called.append("bar")
                return 1

            def get_bar(self):
                return self.__bar

        b = Bar()
        assert b.get_bar() == 1
        assert len(called) == 1

        cached.invalidate(b, "__bar")

        assert b.get_bar() == 1
        assert len(called) == 2

    def test_invalidate_mangled_attribute(self):
        # It should be possible to invalidate a private cached attribute
        # by its mangled name.
        called = []

        class Bar:
            @cached
            def __bar(self):
                called.append("bar")
                return 1

            def get_bar(self):
                return self.__bar

        b = Bar()
        assert b.get_bar() == 1
        assert len(called) == 1

        cached.invalidate(b, "_Bar__bar")

        assert b.get_bar() == 1
        assert len(called) == 2

    def test_invalidate_reserved_attribute(self):
        # It should be possible to invalidate a reserved cached attribute.
        called = []

        class Bar:
            @cached
            def __bar__(self):
                called.append("bar")
                return 1

        b = Bar()
        assert b.__bar__ == 1
        assert len(called) == 1

        cached.invalidate(b, "__bar__")

        assert b.__bar__ == 1
        assert len(called) == 2

    def test_invalidate_uncached_attribute(self):
        # Invalidating an attribute that is not cached should
        # raise an AttributeError.
        called = []

        class Bar:
            def bar(self):
                called.append("bar")
                return 1

        b = Bar()
        with pytest.raises(AttributeError, match="'Bar.bar' is not a cached attribute"):
            cached.invalidate(b, "bar")

    def test_invalidate_uncached_private_attribute(self):
        # Invalidating a private attribute that is not cached should
        # raise an AttributeError.
        called = []

        class Bar:
            def __bar(self):
                called.append("bar")
                return 1

        b = Bar()
        with pytest.raises(
            AttributeError, match="'Bar._Bar__bar' is not a cached attribute"
        ):
            cached.invalidate(
                b,
                "__bar",
            )

    def test_invalidate_unknown_attribute(self):
        # Invalidating an unknown attribute should
        # raise an AttributeError.
        called = []

        class Bar:
            @cached
            def bar(self):
                called.append("bar")
                return 1

        b = Bar()
        with pytest.raises(
            AttributeError, match="type object 'Bar' has no attribute 'baz'"
        ):
            lazy_property.invalidate(
                b,
                "baz",
            )

    def test_invalidate_readonly_object(self):
        # Calling invalidate on a read-only object should
        # raise an AttributeError.
        called = []

        class Bar:
            __slots__ = ()

            @cached
            def bar(self):
                called.append("bar")
                return 1

        b = Bar()
        with pytest.raises(
            AttributeError, match="'Bar' object has no attribute '__dict__'"
        ):
            cached.invalidate(
                b,
                "bar",
            )

    def test_invalidate_superclass_attribute(self):
        # cached.invalidate CANNOT invalidate a superclass (lazy_property) attribute.
        called = []

        class Bar:
            @lazy_property
            def bar(self):
                called.append("bar")
                return 1

        b = Bar()
        with pytest.raises(AttributeError, match="'Bar.bar' is not a cached attribute"):
            cached.invalidate(
                b,
                "bar",
            )

    def test_invalidate_subclass_attribute(self):
        # Whereas lazy_property.invalidate CAN invalidate a subclass (cached) attribute.
        called = []

        class Bar:
            @cached
            def bar(self):
                called.append("bar")
                return 1

        b = Bar()
        assert b.bar == 1
        assert len(called) == 1

        lazy_property.invalidate(b, "bar")

        assert b.bar == 1
        assert len(called) == 2


class TestTryOrReturn:
    def test_decorator(self):
        class A:
            @return_if_raise(ValueError, "hello")
            def return_one(self):
                return 1

            @return_if_raise(ValueError, "hello")
            def return_hello(self):
                raise ValueError

            @return_if_raise(KeyError, "hello")
            def reraise_value_error(self):
                raise ValueError

            @return_if_raise([KeyError, ValueError], "hello")
            def catch_exc_list(self):
                import random

                if random.randint(0, 1) == 0:
                    raise ValueError
                raise KeyError

            @return_none_if_raise(TypeError)
            def return_none(self):
                raise TypeError

        a = A()
        assert a.return_one() == 1
        assert a.return_hello() == "hello"
        with pytest.raises(ValueError):
            a.reraise_value_error()
        assert a.catch_exc_list() == "hello"
        assert a.return_none() is None


class TestTimeout:
    @pytest.mark.skipif(platform.system() == "Windows", reason="Skip on windows")
    def test_with(self):
        try:
            with timeout(1, "timeout!"):
                time.sleep(2)
            raise AssertionError("Did not timeout!")
        except TimeoutError as ex:
            assert ex.message == "timeout!"


class TestProfMain:
    def test_prof_decorator(self):
        """Testing prof_main decorator."""
        import sys

        @prof_main
        def main():
            return sys.exit(1)

        # Have to change argv before calling main.
        # Will restore original values before returning.
        _ = sys.argv[:]
        if len(sys.argv) == 1:
            sys.argv.append("prof")
        else:
            sys.argv[1] = "prof"
