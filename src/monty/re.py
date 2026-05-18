"""Helpful regex based functions. E.g., grepping."""

from __future__ import annotations

import collections
import contextlib
import re
from typing import TYPE_CHECKING

from monty.io import reverse_readfile, zopen

if TYPE_CHECKING:
    from collections.abc import Callable


def regrep(
    filename: str,
    patterns: dict,
    reverse: bool = False,
    terminate_on_match: bool = False,
    postprocess: Callable = str,
) -> dict:
    r"""A powerful regular expression version of grep.

    Args:
        filename (str): Filename to grep.
        patterns (dict): A dict of patterns, e.g.,
            {"energy": r"energy\\(sigma->0\\)\\s+=\\s+([\\d\\-\\.]+)"}.
        reverse (bool): Read files in reverse. Defaults to false. Useful for
            large files, especially when used with terminate_on_match.
        terminate_on_match (bool): Whether to terminate when there is at
            least one match in each key in pattern.
        postprocess (callable): A post processing function to convert all
            matches. Defaults to str, i.e., no change.

    Returns:
        A dict of the following form:
            {key1: [[[matches...], lineno], [[matches...], lineno],
                    [[matches...], lineno], ...],
            key2: ...}
        For reverse reads, the lineno is given as a -ve number. Please note
        that 0-based indexing is used.
    """
    compiled = [(k, re.compile(v)) for k, v in patterns.items()]
    matches: dict[str, list] = collections.defaultdict(list)
    # ``pending`` lets ``terminate_on_match`` short-circuit in O(1) per line
    # instead of re-scanning every key in ``compiled``.
    pending: set[str] | None = {k for k, _ in compiled} if terminate_on_match else None
    gen = (
        reverse_readfile(filename)
        if reverse
        else zopen(filename, mode="rt", encoding="utf-8")
    )
    for i, line in enumerate(gen):
        lineno = -i if reverse else i
        for k, p in compiled:
            if m := p.search(line):
                matches[k].append([[postprocess(g) for g in m.groups()], lineno])
                if pending is not None:
                    pending.discard(k)
        if pending is not None and not pending:
            break

    with contextlib.suppress(Exception):
        # Try to close open file handle. Pass if it is a generator.
        gen.close()  # type: ignore[attr-defined, union-attr]
    return matches
