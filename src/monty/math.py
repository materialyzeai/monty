"""Addition math functions."""

from __future__ import annotations

import math

from monty.dev import deprecated


@deprecated(replacement="math.comb", deadline=(2028, 1, 1))
def nCr(n: int, r: int) -> int:
    """Calculates nCr (binomial coefficient or "n choose r").

    Args:
        n (int): total number of items.
        r (int): items to choose

    Returns:
        nCr.

    """
    return math.comb(n, r)


@deprecated(replacement="math.perm", deadline=(2028, 1, 1))
def nPr(n: int, r: int) -> int:
    """Calculates nPr.

    Args:
        n (int): total number of items.
        r (int): items to permute

    Returns:
        nPr.

    """
    return math.perm(n, r)
