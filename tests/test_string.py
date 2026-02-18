from __future__ import annotations

import random

from monty.string import remove_non_ascii


def test_remove_non_ascii():
    s = "".join(chr(random.randint(0, 127)) for _ in range(10))
    s += "".join(chr(random.randint(128, 150)) for _ in range(10))
    clean = remove_non_ascii(s)
    assert len(clean) == 10
