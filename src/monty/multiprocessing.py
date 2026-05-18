"""Multiprocessing utilities."""

from __future__ import annotations

from multiprocessing import Pool
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

try:
    from tqdm.autonotebook import tqdm
except ImportError as exc:
    raise ImportError("tqdm must be installed for this function.") from exc


def imap_tqdm(nprocs: int, func: Callable, iterable: Iterable, *args, **kwargs) -> list:
    """Run ``Pool.imap`` over ``iterable`` with a ``tqdm`` progress bar.

    Args:
        nprocs: Number of processes.
        func: Callable applied to each item.
        iterable: Iterable of arguments.
        args: Passthrough to ``Pool.imap``.
        kwargs: Passthrough to ``Pool.imap``.

    Returns:
        Results of ``Pool.imap``.

    """
    data = []
    with Pool(nprocs) as pool:
        try:
            n = len(iterable)  # type: ignore[arg-type]
        except TypeError:
            n = None  # type: ignore[arg-type]
        with tqdm(total=n) as prog_bar:
            for d in pool.imap(func, iterable, *args, **kwargs):
                prog_bar.update()
                data.append(d)
    return data
