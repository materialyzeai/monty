"""Monty is the missing complement to Python. Monty implements supplementary
useful functions for Python that are not part of the standard library.
Examples include useful utilities like transparent support for zipped files,
useful design patterns such as singleton and cached_class, and many more.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2014, The Materials Virtual Lab"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__date__ = "Oct 12 2020"

try:
    __version__ = version("monty")
except PackageNotFoundError:  # pragma: no cover
    # package is not installed
    pass
