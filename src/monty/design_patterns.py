"""Some common design patterns such as singleton and cached classes."""

from __future__ import annotations

import inspect
import os
from functools import wraps
from typing import TYPE_CHECKING, TypeVar
from weakref import WeakValueDictionary

if TYPE_CHECKING:
    from typing import Any


def singleton(cls):
    """This decorator can be used to create a singleton out of a class.

    Usage:
        @singleton
        class MySingleton():

            def __init__():
                pass
    """
    instances = {}

    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]

    return getinstance


# https://github.com/microsoft/pylance-release/issues/3478
Klass = TypeVar("Klass")


def cached_class(cls: type[Klass]) -> type[Klass]:
    """Decorator to cache class instances by constructor arguments.
    This results in a class that behaves like a singleton for each
    set of constructor arguments, ensuring efficiency.

    Note that this should be used for *immutable classes only*.  Having
    a cached mutable class makes very little sense.  For efficiency,
    avoid using this decorator for situations where there are many
    constructor arguments permutations.

    If any arguments are non-hashable, that set of arguments
    is not cached.
    """
    orig_new = cls.__new__
    orig_init = cls.__init__
    cache: WeakValueDictionary = WeakValueDictionary()

    @wraps(orig_new)
    def new_new(cls, *args: Any, **kwargs: Any) -> Any:
        # Normalize arguments
        sig = inspect.signature(orig_init)
        bound_args = sig.bind(None, *args, **kwargs)
        bound_args.apply_defaults()

        # Remove 'self' from the arguments
        normalized_args = tuple(bound_args.arguments.values())[1:]

        try:
            key = (cls, normalized_args)
            if key in cache:
                return cache[key]

            if orig_new is object.__new__:
                instance = orig_new(cls)
            else:
                instance = orig_new(cls, *args, **kwargs)

            orig_init(instance, *args, **kwargs)
            instance._initialized = True
            cache[key] = instance
            return instance
        except TypeError:
            # Can't cache this set of arguments
            if orig_new is object.__new__:
                instance = orig_new(cls)
            else:
                instance = orig_new(cls, *args, **kwargs)
            orig_init(instance, *args, **kwargs)
            instance._initialized = True
            return instance

    @wraps(orig_init)
    def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
        if not hasattr(self, "_initialized"):
            orig_init(self, *args, **kwargs)
            self._initialized = True

    def reduce(self: Any) -> tuple[type, tuple, dict[str, Any]]:
        for key, value in cache.items():
            if value is self:
                cls, args = key
                return (cls, args, {})
        raise ValueError("Instance not found in cache")

    cls.__new__ = new_new  # type: ignore[method-assign]
    cls.__init__ = new_init  # type: ignore[method-assign]
    cls.__reduce__ = reduce  # type: ignore[method-assign]

    return cls


class NullFile:
    """A file object that is associated to /dev/null."""

    def __new__(cls):
        """Pass through."""
        return open(os.devnull, "w")  # pylint: disable=R1732

    def __init__(self):
        """no-op."""


class NullStream:
    """A fake stream with a no-op write."""

    def write(self, *args):  # pylint: disable=E0211
        """Does nothing..."""
