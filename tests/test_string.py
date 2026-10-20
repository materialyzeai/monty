from __future__ import annotations

import random

from monty.string import remove_non_ascii


def test_remove_non_ascii():
    s = "".join(chr(random.randint(0, 127)) for _ in range(10))
    s += "".join(chr(random.randint(128, 150)) for _ in range(10))
    clean = remove_non_ascii(s)
    assert len(clean) == 10


def test_remove_non_ascii_preserves_order():
    assert remove_non_ascii("caf\u00e9 \u2014 na\u00efve\x7f") == "caf  nave\x7f"
