"""Os functions, e.g., cd, makedirs_p."""

from __future__ import annotations

import errno
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

    from monty.shutil import PathLike

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2013, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__date__ = "1/24/14"


@contextmanager
def cd(path: PathLike) -> Generator:
    """Fabric-inspired context manager that temporarily changes directory.

    The working directory is restored on exit.

    Examples:
        >>> with cd("/my/path/"):
        ...     do_something()

    Args:
        path: Path to ``cd`` to.

    """
    cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)


def makedirs_p(path: PathLike, **kwargs) -> None:
    """Thread-safe ``os.makedirs`` that tolerates an existing directory.

    Mirrors the behaviour of ``mkdir -p``.

    Args:
        path: Path of the directory to create.
        kwargs: Standard kwargs for ``os.makedirs``.

    """
    try:
        os.makedirs(path, **kwargs)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise
