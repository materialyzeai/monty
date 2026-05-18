"""This module provides support for Unix shell-style wildcards."""

from __future__ import annotations

import fnmatch
import re

from monty.string import list_strings


class WildCard:
    """This object provides an easy-to-use interface for filename matching with
    shell patterns (fnmatch).

    >>> w = WildCard("*.nc|*.pdf")
    >>> w.filter(["foo.nc", "bar.pdf", "hello.txt"])
    ['foo.nc', 'bar.pdf']

    >>> w.filter("foo.nc")
    ['foo.nc']
    """

    def __init__(self, wildcard: str, sep: str = "|") -> None:
        """Initializes a WildCard.

        Args:
            wildcard (str): String of tokens separated by sep. Each token
                represents a pattern.
            sep (str): Separator for shell patterns.
        """
        self.pats: list[str] = wildcard.split(sep) if wildcard else ["*"]
        # Pre-compile each pattern once so per-call matching does not pay the
        # ``fnmatch.translate`` cost (only an internal LRU cache otherwise).
        self._regexes: list[re.Pattern[str]] = [
            re.compile(fnmatch.translate(p)) for p in self.pats
        ]

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}, patterns = {self.pats}>"

    def filter(self, names: list[str]) -> list[str]:
        """Return a list with the names matching the pattern.

        Note: a name that matches multiple patterns is repeated once per
        match in the result (preserved for backward compatibility).
        """
        regexes = self._regexes
        return [
            filename
            for filename in list_strings(names)
            for regex in regexes
            if regex.match(filename)
        ]

    def match(self, name: str) -> bool:
        """Returns True if name matches one of the patterns."""
        return any(regex.match(name) for regex in self._regexes)
