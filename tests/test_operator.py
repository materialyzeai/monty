from __future__ import annotations

import pytest

from monty.operator import operator_from_str


def test_operator_from_str():
    assert operator_from_str("==")(1, 1)
    assert operator_from_str("+")(1, 1) == 2


@pytest.mark.parametrize(
    ("op", "expected"),
    [
        ("!=", True),
        (">", False),
        (">=", False),
        ("<", True),
        ("<=", True),
        ("-", -1),
        ("*", 2),
        ("%", 1),
        ("^", 3),
        ("/", 0.5),
    ],
)
def test_operator_from_str_all(op, expected):
    assert operator_from_str(op)(1, 2) == expected


def test_operator_from_str_invalid():
    with pytest.raises(KeyError):
        operator_from_str("**")
