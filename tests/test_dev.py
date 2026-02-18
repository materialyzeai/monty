from __future__ import annotations

import unittest
import warnings
from dataclasses import dataclass

import pytest

from monty.dev import deprecated, install_excepthook, requires

try:
    from IPython.core import ultratb
except ImportError:
    ultratb = None

# Set all warnings to always be triggered.
warnings.simplefilter("always")


class TestDeprecated:
    def test_basic_usage(self):
        def func_replace():
            pass

        @deprecated(func_replace, "Use func_replace instead", deadline=(2025, 1, 1))
        def func_old():
            """This is the old function."""
            pass

        with warnings.catch_warnings(record=True) as w:
            # Trigger a warning.
            func_old()

            assert issubclass(w[0].category, FutureWarning)
            assert "Use func_replace instead" in str(w[0].message)
            assert "will be removed on 2025-01-01" in str(w[0].message)

        # Check metadata preservation
        assert func_old.__name__ == "func_old"
        assert func_old.__doc__ == "This is the old function."

    def test_str_replacement(self):
        @deprecated("func_replace")
        def func_old():
            pass

        with warnings.catch_warnings(record=True) as w:
            # Trigger a warning.
            func_old()
            # Verify Warning and message
            assert issubclass(w[0].category, FutureWarning)
            assert "use func_replace instead" in str(w[0].message)

    def test_property(self):
        class TestClass:
            """A dummy class for tests."""

            @property
            def property_a(self):
                pass

            @property
            @deprecated(property_a)
            def property_b(self):
                return "b"

            @deprecated(property_a)
            def func_a(self):
                return "a"

        with warnings.catch_warnings(record=True) as w:
            # Trigger a warning.
            assert TestClass().property_b == "b"
            # Verify warning type
            assert issubclass(w[-1].category, FutureWarning)

        with warnings.catch_warnings(record=True) as w:
            # Trigger a warning.
            assert TestClass().func_a() == "a"
            # Verify some things
            assert issubclass(w[-1].category, FutureWarning)

    def test_classmethod(self):
        class TestClass:
            """A dummy class for tests."""

            @classmethod
            def classmethod_a(cls):
                pass

            @classmethod
            @deprecated(classmethod_a)
            def classmethod_b(cls):
                return "b"

        with warnings.catch_warnings(record=True) as w:
            # Trigger a warning.
            assert TestClass().classmethod_b() == "b"
            # Verify some things
            assert issubclass(w[-1].category, FutureWarning)

        class TestClass_deprecationwarning:
            """A dummy class for tests."""

            @classmethod
            def classmethod_a(cls):
                pass

            @classmethod
            @deprecated(classmethod_a, category=DeprecationWarning)
            def classmethod_b(cls):
                return "b"

        with pytest.warns(DeprecationWarning):
            assert TestClass_deprecationwarning().classmethod_b() == "b"

    def test_class(self):
        class TestClassNew:
            """A dummy class for tests."""

            def method_a(self):
                pass

        @deprecated(replacement=TestClassNew)
        class TestClassOld:
            """A dummy old class for tests."""

            class_attrib_old = "OLD_ATTRIB"

            def method_b(self):
                """This is method_b."""
                pass

        with pytest.warns(FutureWarning, match="TestClassOld is deprecated"):
            old_class = TestClassOld()

        # Check metadata preservation
        assert old_class.__doc__ == "A dummy old class for tests."
        assert old_class.class_attrib_old == "OLD_ATTRIB"
        assert old_class.__module__ == __name__

        assert old_class.method_b.__doc__ == "This is method_b."

    def test_dataclass(self):
        @dataclass
        class TestClassNew:
            """A dummy class for tests."""

            def __post_init__(self):
                pass

            def method_a(self):
                pass

        @deprecated(replacement=TestClassNew)
        @dataclass
        class TestClassOld:
            """A dummy old class for tests."""

            class_attrib_old = "OLD_ATTRIB"

            def __post_init__(self):
                pass

            def method_b(self):
                """This is method_b."""
                pass

        with pytest.warns(FutureWarning, match="TestClassOld is deprecated"):
            old_class = TestClassOld()

        # Check metadata preservation
        assert old_class.__doc__ == "A dummy old class for tests."
        assert old_class.class_attrib_old == "OLD_ATTRIB"


def test_requires():
    try:
        import fictitious_mod
    except ImportError:
        fictitious_mod = None

    err_msg = "fictitious_mod is not present."

    @requires(fictitious_mod is not None, err_msg)
    def use_fictitious_mod():
        pass

    with pytest.raises(RuntimeError, match=err_msg):
        use_fictitious_mod()

    @requires(unittest is not None, "unittest is not present.")
    def use_unittest():
        return "success"

    assert use_unittest() == "success"

    # test with custom error class
    @requires(False, "expect ImportError", err_cls=ImportError)
    def use_import_error():
        return "success"

    with pytest.raises(ImportError, match="expect ImportError"):
        use_import_error()


@pytest.mark.skipif(ultratb is None, reason="ipython is not installed")
def test_install_except_hook():
    install_excepthook()
