from __future__ import annotations

import pytest

from monty.itertools import chunks, ilotri, iterator_from_slice, iuptri


def _ref_tri(items, diago, with_inds, upper):
    items = list(items)
    for ii, item1 in enumerate(items):
        jjs = range(ii if diago else ii + 1, len(items)) if upper else range(ii + diago)
        for jj in jjs:
            yield ((ii, jj), (item1, items[jj])) if with_inds else (item1, items[jj])


def test_iterator_from_slice():
    assert list(iterator_from_slice(slice(0, 6, 2))) == [0, 2, 4]


def test_chunks():
    assert list(chunks(range(1, 25), 10)) == [
        (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
        (11, 12, 13, 14, 15, 16, 17, 18, 19, 20),
        (21, 22, 23, 24),
    ]


@pytest.mark.parametrize("items", [[], ["a"], ["a", "b", "c", "d"]])
@pytest.mark.parametrize("diago", [True, False])
@pytest.mark.parametrize("with_inds", [True, False])
@pytest.mark.parametrize(("func", "upper"), [(iuptri, True), (ilotri, False)])
def test_triangles(items, diago, with_inds, func, upper):
    expected = list(_ref_tri(items, diago, with_inds, upper))
    # Accepts any iterable, not only sequences.
    assert list(func(iter(items), diago=diago, with_inds=with_inds)) == expected


def test_iuptri_order():
    assert list(iuptri([0, 1, 2], diago=False)) == [(0, 1), (0, 2), (1, 2)]
    assert list(iuptri([0, 1], with_inds=True)) == [
        ((0, 0), (0, 0)),
        ((0, 1), (0, 1)),
        ((1, 1), (1, 1)),
    ]
