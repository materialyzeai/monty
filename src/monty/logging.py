"""Logging tools."""

from __future__ import annotations

import argparse
import datetime
import functools
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def logged(level: int = logging.DEBUG) -> Callable:
    """Decorator that logs the start and end of a method call.

    Args:
        level: Level to log method at. Defaults to ``DEBUG``.

    """

    def wrap(f):
        _logger = logging.getLogger(f"{f.__module__}.{f.__name__}")

        def wrapped_f(*args, **kwargs):
            _logger.log(
                level,
                f"Called at {datetime.datetime.now()} with args = {args} and kwargs = {kwargs}",
            )
            data = f(*args, **kwargs)
            _logger.log(
                level,
                f"Done at {datetime.datetime.now()} with args = {args} and kwargs = {kwargs}",
            )
            return data

        return wrapped_f

    return wrap


def enable_logging(main: Callable) -> Callable:
    """Decorator that initializes logging with a ``--loglevel`` CLI option.

    Useful for simple main functions calling libraries that use the standard
    ``logging`` module.

    Args:
        main: The main function.

    """

    @functools.wraps(main)
    def wrapper(*args, **kwargs):
        parser = argparse.ArgumentParser()

        parser.add_argument(
            "--loglevel",
            default="ERROR",
            type=str,
            help="Set the loglevel. Possible values: CRITICAL, ERROR (default),"
            "WARNING, INFO, DEBUG",
        )

        options = parser.parse_args()

        # loglevel is bound to the string value obtained from the command line
        # argument.
        # Convert to upper case to allow the user to specify --loglevel=DEBUG
        # or --loglevel=debug
        numeric_level = getattr(logging, options.loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {options.loglevel}")
        logging.basicConfig(level=numeric_level)

        return main(*args, **kwargs)

    return wrapper
