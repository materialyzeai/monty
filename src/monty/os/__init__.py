"""Os functions, e.g., cd, makedirs_p."""

from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING

from monty.dev import deprecated

if TYPE_CHECKING:
    from monty.shutil import PathLike

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2013, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__date__ = "1/24/14"


@deprecated(replacement="contextlib.chdir", deadline=(2028, 1, 1))
def cd(path: PathLike) -> contextlib.chdir:
    """Context manager that temporarily changes the working directory.

    The working directory is restored on exit. Equivalent to
    ``contextlib.chdir``.

    Examples:
        >>> with cd("/my/path/"):
        ...     do_something()

    Args:
        path: Path to ``cd`` to.

    """
    return contextlib.chdir(path)


@deprecated(replacement="os.makedirs(path, exist_ok=True)", deadline=(2028, 1, 1))
def makedirs_p(path: PathLike, **kwargs) -> None:
    """Thread-safe ``os.makedirs`` that tolerates an existing directory.

    Mirrors the behaviour of ``mkdir -p``. Equivalent to
    ``os.makedirs(path, exist_ok=True)``.

    Args:
        path: Path of the directory to create.
        kwargs: Standard kwargs for ``os.makedirs``.

    """
    os.makedirs(path, exist_ok=True, **kwargs)
