from __future__ import annotations

import pytest

from monty.bisect import find_ge, find_gt, find_le, find_lt, index


def test_funcs():
    line = [0, 1, 2, 3, 4]
    assert index(line, 1) == 1
    assert find_lt(line, 1) == 0
    assert find_gt(line, 1) == 2
    assert find_le(line, 1) == 1
    assert find_ge(line, 2) == 2


@pytest.mark.parametrize(
    ("x", "atol", "expected"),
    [
        (1.501, 0.1, 2),
        (1.499, 0.1, 2),
        (2.0001, 1e-3, 3),  # Just above an element.
        (1.9999, 1e-3, 3),  # Just below an element.
        (1.2, 0.5, 1),  # Leftmost of several values within tolerance.
    ],
)
def test_index_atol(x, atol, expected):
    assert index([0, 1, 1.5, 2], x, atol=atol) == expected


@pytest.mark.parametrize(
    ("func", "x"),
    [
        (index, 1.5),
        (index, 5),
        (find_lt, 0),
        (find_le, -1),
        (find_gt, 4),
        (find_ge, 5),
    ],
)
def test_not_found(func, x):
    with pytest.raises(ValueError):
        func([0, 1, 2, 3, 4], x)


def test_index_atol_not_found():
    with pytest.raises(ValueError):
        index([0, 1, 2], 2.5, atol=0.1)
    # Tolerance is strict.
    with pytest.raises(ValueError):
        index([0, 1, 2], 2.5, atol=0.5)
