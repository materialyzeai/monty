"""This module provides support for Unix shell-style wildcards."""

from __future__ import annotations

import fnmatch

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
        self.pats = wildcard.split(sep) if wildcard else ["*"]

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}, patterns = {self.pats}>"

    def filter(self, names: list[str]) -> list[str]:
        """Returns a list with the names matching the pattern."""
        names = list_strings(names)

        filenames = []
        for filename in names:
            for pat in self.pats:
                if fnmatch.fnmatch(filename, pat):
                    filenames.append(filename)

        return filenames

    def match(self, name: str) -> bool:
        """Returns True if name matches one of the patterns."""
        return any(fnmatch.fnmatch(name, pat) for pat in self.pats)
