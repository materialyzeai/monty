"""Additional tools for iteration."""

from __future__ import annotations

import itertools
import sys
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterable


# Use stdlib batched on 3.12+, fall back to local impl otherwise.
_HAS_BATCHED = sys.version_info >= (3, 12)


def chunks(items: Iterable, n: int) -> Iterable:
    """Yield successive n-sized chunks from a list-like object.

    >>> import pprint
    >>> pprint.pprint(list(chunks(range(1, 25), 10)))
    [(1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
     (11, 12, 13, 14, 15, 16, 17, 18, 19, 20),
     (21, 22, 23, 24)]
    """
    if _HAS_BATCHED:
        yield from itertools.batched(items, n)  # type: ignore[attr-defined]
        return

    it = iter(items)
    chunk = tuple(itertools.islice(it, n))
    while chunk:
        yield chunk
        chunk = tuple(itertools.islice(it, n))


def iterator_from_slice(s) -> Iterable:
    """Constructs an iterator given a slice object s.

    Notes:
        The function returns an infinite iterator if s.stop is None
    """
    start = s.start if s.start is not None else 0
    step = s.step if s.step is not None else 1

    if s.stop is None:
        # Infinite iterator.
        return itertools.count(start=start, step=step)

    # xrange-like iterator that supports float.
    return iter(np.arange(start, s.stop, step))


def iuptri(
    items: Iterable, diago: bool = True, with_inds: bool = False
) -> Iterable:
    """A generator that yields the upper triangle of the matrix (items x items).

    Args:
        items: Iterable object with elements [e0, e1, ...]
        diago: False if diagonal matrix elements should be excluded
        with_inds: If True, (i,j) (e_i, e_j) is returned else (e_i, e_j)

    >>> for (ij, mate) in iuptri([0,1], with_inds=True):
    ...     print("ij:", ij, "mate:", mate)
    ij: (0, 0) mate: (0, 0)
    ij: (0, 1) mate: (0, 1)
    ij: (1, 1) mate: (1, 1)
    """
    items = list(items)
    n = len(items)
    offset = 0 if diago else 1
    for ii in range(n):
        item1 = items[ii]
        for jj in range(ii + offset, n):
            if with_inds:
                yield (ii, jj), (item1, items[jj])
            else:
                yield item1, items[jj]


def ilotri(
    items: Iterable, diago: bool = True, with_inds: bool = False
) -> Iterable:
    """A generator that yields the lower triangle of the matrix (items x items).

    Args:
        items: Iterable object with elements [e0, e1, ...]
        diago: False if diagonal matrix elements should be excluded
        with_inds: If True, (i,j) (e_i, e_j) is returned else (e_i, e_j)

    >>> for (ij, mate) in ilotri([0,1], with_inds=True):
    ...     print("ij:", ij, "mate:", mate)
    ij: (0, 0) mate: (0, 0)
    ij: (1, 0) mate: (1, 0)
    ij: (1, 1) mate: (1, 1)
    """
    items = list(items)
    n = len(items)
    extra = 1 if diago else 0
    for ii in range(n):
        item1 = items[ii]
        for jj in range(ii + extra):
            if with_inds:
                yield (ii, jj), (item1, items[jj])
            else:
                yield item1, items[jj]
