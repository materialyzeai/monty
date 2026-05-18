"""Math functions."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def gcd(*numbers: int) -> int:
    """Returns the greatest common divisor for a sequence of numbers.

    Args:
        *numbers: Sequence of numbers.

    Returns:
        int: Greatest common divisor of numbers.
    """
    return math.gcd(*numbers)


def lcm(*numbers: int) -> int:
    """Return lowest common multiple of a sequence of numbers.

    Args:
        *numbers: Sequence of numbers.

    Returns:
        int: Lowest common multiple of numbers.
    """
    return math.lcm(*numbers)


def gcd_float(numbers: Sequence[float], tol: float = 1e-8) -> float:
    """Returns the greatest common divisor for a sequence of numbers.
    Uses a numerical tolerance, so can be used on floats.

    Args:
        numbers: Sequence of numbers.
        tol: Numerical tolerance

    Returns:
        float: Greatest common divisor of numbers.
    """

    def pair_gcd_tol(a: float, b: float) -> float:
        """Calculate the Greatest Common Divisor of a and b.

        Unless b==0, the result will have the same sign as b (so that when
        b is divided by it, the result comes out positive).
        """
        while b > tol:
            a, b = b, a % b
        return a

    n = numbers[0]
    for i in numbers[1:]:
        n = pair_gcd_tol(n, i)
    return n
