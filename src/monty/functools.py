"""functools, especially backported from Python 3."""

from __future__ import annotations

import cProfile
import pstats
import signal
import sys
import tempfile
from functools import partial, wraps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Union
    from collections.abc import Callable


class _HashedSeq(list):
    """This class guarantees that hash() will be called no more than once
    per element.  This is important because the lru_cache() will hash
    the key multiple times on a cache miss.
    """

    __slots__ = ("hashvalue",)

    def __init__(self, tup: tuple, hashfunc: Callable = hash) -> None:
        """Args:
        tup: Tuple.
        hashfunc: Hash function.
        """
        self[:] = tup
        self.hashvalue: int = hashfunc(tup)

    def __hash__(self) -> int:  # type: ignore[override]
        return self.hashvalue


def _make_key(
    args: tuple,
    kwds: dict,
    typed: bool,
    kwd_mark: tuple[object] = (object(),),
    fasttypes=None,
) -> Any:
    """Make a cache key from optionally typed positional and keyword arguments.

    The key is constructed in a way that is flat as possible rather than
    as a nested structure that would take more memory.

    If there is only a single argument and its data type is known to cache
    its hash value, then that argument is returned without a wrapper.  This
    saves space and improves lookup speed.
    """
    key = args
    if kwds:
        sorted_items = sorted(kwds.items())
        key += kwd_mark
        for item in sorted_items:
            key += item
    if typed:
        key += tuple(type(v) for v in args)
        if kwds:
            key += tuple(type(v) for k, v in sorted_items)
    elif len(key) == 1 and isinstance(key[0], fasttypes):
        return key[0]
    return _HashedSeq(key)


class lazy_property:
    """lazy_property descriptor.

    Used as a decorator to create lazy attributes. Lazy attributes
    are evaluated on first use.
    """

    def __init__(self, func: Callable) -> None:
        """Args:
        func: Function to decorate.
        """
        self.__func = func
        wraps(self.__func)(self)  # type: ignore[arg-type]

    def __get__(self, inst: Any, inst_cls) -> Any:
        if inst is None:
            return self

        if not hasattr(inst, "__dict__"):
            raise AttributeError(
                f"'{inst_cls.__name__}' object has no attribute '__dict__'"
            )

        name = self.__name__  # type: ignore[attr-defined]  # pylint: disable=E1101
        if name.startswith("__") and not name.endswith("__"):
            name = f"_{inst_cls.__name__}{name}"

        value = self.__func(inst)
        inst.__dict__[name] = value
        return value

    @classmethod
    def invalidate(cls, inst: object, name: str) -> None:
        """Invalidate a lazy attribute.

        This obviously violates the lazy contract. A subclass of lazy
        may however have a contract where invalidation is appropriate.
        """
        inst_cls = inst.__class__

        if not hasattr(inst, "__dict__"):
            raise AttributeError(
                f"'{inst_cls.__name__}' object has no attribute '__dict__'"
            )

        if name.startswith("__") and not name.endswith("__"):
            name = f"_{inst_cls.__name__}{name}"

        if not isinstance(getattr(inst_cls, name), cls):
            raise AttributeError(
                f"'{inst_cls.__name__}.{name}' is not a {cls.__name__} attribute"
            )

        if name in inst.__dict__:
            del inst.__dict__[name]


def return_if_raise(
    exception_tuple: list | tuple, retval_if_exc: Any, disabled: bool = False
) -> Any:
    """Decorator for functions, methods or properties. Execute the callable in a
    try block, and return retval_if_exc if one of the exceptions listed in
    exception_tuple is raised (se also ``return_node_if_raise``).

    Setting disabled to True disables the try except block (useful for
    debugging purposes). One can use this decorator to define properties.

    Examples:
        @return_if_raise(ValueError, None)
        def return_none_if_value_error(self):
            pass

        @return_if_raise((ValueError, KeyError), "hello")
        def another_method(self):
            pass

        @property
        @return_if_raise(AttributeError, None)
        def name(self):
            "Name of the object, None if not set."
            return self._name

    """
    # we need a tuple of exceptions.
    if isinstance(exception_tuple, list):
        exception_tuple = tuple(exception_tuple)
    elif not isinstance(exception_tuple, tuple):
        exception_tuple = (exception_tuple,)
    else:
        raise TypeError(f"Wrong exception_tuple {type(exception_tuple)}")

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if disabled:
                return func(*args, **kwargs)
            try:
                return func(*args, **kwargs)
            except exception_tuple:  # pylint: disable=E0712
                return retval_if_exc

        return wrapper

    return decorator


# One could use None as default value in return_if_raise but this one is
# explicit and  more readable
return_none_if_raise = partial(return_if_raise, retval_if_exc=None)
"""
This decorator returns None if one of the exceptions is raised.

    @return_none_if_raise(ValueError)
    def method(self):
"""


class timeout:
    """Timeout function. Use to limit matching to a certain time limit. Note that
    this works only on Unix-based systems as it uses signal.

    Usage:
        try:
            with timeout(3):
                do_stuff()
        except TimeoutError:
            do_something_else()
    """

    def __init__(self, seconds: int = 1, error_message: str = "Timeout"):
        """Args:
        seconds (int): Allowed time for function in seconds.
        error_message (str): An error message.

        """
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum: int, frame: Any) -> None:
        """Signal handler that raises TimeoutError.

        Args:
            signum: Return signal from call.
            frame: Current stack frame.
        """
        raise TimeoutError(self.error_message)

    def __enter__(self) -> None:
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type: Any, value: Any, traceback: Any) -> None:  # noqa: A002
        signal.alarm(0)


class TimeoutError(Exception):
    """Exception class for timeouts."""

    def __init__(self, message: str):
        """Args:
        message: Error message.
        """
        self.message = message


def prof_main(main: Callable) -> Callable:
    """Decorator for profiling main programs.

    Profiling is activated by prepending the command line options
    supported by the original main program with the keyword `prof`.

    Examples:
            $ script.py arg --foo=1

        becomes

            $ script.py prof arg --foo=1

        The decorated main accepts two new arguments:

            prof_file: Name of the output file with profiling data
                If not given, a temporary file is created.
            sortby: Profiling data are sorted according to this value.
                default is "time". See sort_stats.
    """

    @wraps(main)
    def wrapper(*args, **kwargs):
        try:
            do_prof = sys.argv[1] == "prof"
            if do_prof:
                sys.argv.pop(1)
        except Exception:
            do_prof = False

        if not do_prof:
            sys.exit(main())
        else:
            print("Entering profiling mode...")
            prof_file = kwargs.get("prof_file")
            if prof_file is None:
                _, prof_file = tempfile.mkstemp()
                print(f"Profiling data stored in {prof_file}")

            sortby = kwargs.get("sortby", "time")
            cProfile.runctx("main()", globals(), locals(), prof_file)
            s = pstats.Stats(prof_file)
            s.strip_dirs().sort_stats(sortby).print_stats()
            if "retval" not in kwargs:
                sys.exit(0)
            else:
                return kwargs["retval"]

    return wrapper
