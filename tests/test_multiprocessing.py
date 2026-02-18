from __future__ import annotations

from math import sqrt

import pytest

try:
    from tqdm.autonotebook import tqdm

    from monty.multiprocessing import imap_tqdm
except ImportError:
    tqdm = None


@pytest.mark.skipif(tqdm is None, reason="tqdm not installed")
def test_imap_tqdm():
    results = imap_tqdm(4, sqrt, range(10_000))
    assert len(results) == 10_000
    assert results[0] == 0
    assert results[400] == 20
    assert results[9999] == 99.99499987499375
    results = imap_tqdm(4, sqrt, (i**2 for i in range(10_000)))
    assert len(results) == 10_000
    assert results[0] == 0
    assert results[400] == 400
