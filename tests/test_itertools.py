from __future__ import annotations

from monty.itertools import chunks, iterator_from_slice


def test_iterator_from_slice():
    assert list(iterator_from_slice(slice(0, 6, 2))) == [0, 2, 4]


def test_chunks():
    assert list(chunks(range(1, 25), 10)) == [
        (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
        (11, 12, 13, 14, 15, 16, 17, 18, 19, 20),
        (21, 22, 23, 24),
    ]
