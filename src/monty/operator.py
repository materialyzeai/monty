"""
Useful additional functions for operators
"""

from __future__ import annotations

import contextlib
import operator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def operator_from_str(op: str) -> Callable:
    """
    Return the operator associated to the given string `op`.

    raises:
        `KeyError` if invalid string.
    """
    d = {
        "==": operator.eq,
        "!=": operator.ne,
        ">": operator.gt,
        ">=": operator.ge,
        "<": operator.lt,
        "<=": operator.le,
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "%": operator.mod,
        "^": operator.xor,
    }

    with contextlib.suppress(AttributeError):
        d["/"] = operator.truediv

    return d[op]
