"""Addition math functions."""

from __future__ import annotations

import math


def nCr(n: int, r: int) -> int:
    """Calculates nCr (binomial coefficient or "n choose r").

    Args:
        n (int): total number of items.
        r (int): items to choose

    Returns:
        nCr.
    """
    f = math.factorial
    return int(f(n) / f(r) / f(n - r))


def nPr(n: int, r: int) -> int:
    """Calculates nPr.

    Args:
        n (int): total number of items.
        r (int): items to permute

    Returns:
        nPr.
    """
    f = math.factorial
    return int(f(n) / f(n - r))
