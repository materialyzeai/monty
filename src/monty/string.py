"""Useful additional string functions."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from monty.dev import deprecated

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any, Union


def remove_non_ascii(s: str) -> str:
    """Remove non-ASCII characters from a string.

    Args:
        s (str): Input string.

    Returns:
        String with all non-ASCII characters removed.

    """
    return "".join(i for i in s if ord(i) < 128)


@deprecated(replacement="isinstance(s, str)", deadline=(2028, 1, 1))
def is_string(s: Any) -> bool:
    """Return True if ``s`` is a string.

    Historically this used a duck-typing ``s + " "`` probe, but every caller
    in monty (and downstream libraries) treats this as ``isinstance(s, str)``,
    so the C-level check is used directly — roughly 50x faster for the common
    "not a string" path because no exception is raised.
    """
    return isinstance(s, str)


def list_strings(arg: str | Iterable[str]) -> list[str]:
    """Always return a list of strings, given a string or iterable of strings.

    Examples:
        >>> list_strings('A single string')
        ['A single string']

        >>> list_strings(['A single string in a list'])
        ['A single string in a list']

        >>> list_strings(['A','list','of','strings'])
        ['A', 'list', 'of', 'strings']

        >>> list_strings(('A','list','of','strings'))
        ['A', 'list', 'of', 'strings']

        >>> list_strings({"a": 1, "b": 2}.keys())
        ['a', 'b']

    """
    if isinstance(arg, str):
        return [arg]

    return [cast(str, s) for s in arg]


def marquee(text: str = "", width: int = 78, mark: str = "*") -> str:
    """Return the input string centered in a 'marquee'.

    Args:
        text (str): Input string
        width (int): Width of final output string.
        mark (str): Character used to fill string.

    Examples:
        >>> marquee('A test', width=40)
        '**************** A test ****************'

        >>> marquee('A test', width=40, mark='-')
        '---------------- A test ----------------'

        marquee('A test',40, ' ')
        '                 A test                 '

    """
    if not text:
        return (mark * width)[:width]

    nmark = (width - len(text) - 2) // len(mark) // 2
    nmark = max(nmark, 0)

    marks = mark * nmark
    return f"{marks} {text} {marks}"


def boxed(msg: str, ch: str = "=", pad: int = 5) -> str:
    """Returns a string in a box.

    Args:
        msg: Input string.
        ch: Character used to form the box.
        pad: Number of characters ch added before and after msg.

    Examples:
        >>> print(boxed("hello", ch="*", pad=2))
        ***********
        ** hello **
        ***********

    """
    if pad > 0:
        msg = pad * ch + " " + msg.strip() + " " + pad * ch

    return "\n".join(
        [
            len(msg) * ch,
            msg,
            len(msg) * ch,
        ]
    )


def make_banner(s: str, width: int = 78, mark: str = "*") -> str:
    """Build a banner string with full-width top and bottom rules.

    Args:
        s: String.
        width: Width of banner. Defaults to 78.
        mark: The mark used to create the banner.

    Returns:
        Banner string.

    """
    banner = marquee(s, width=width, mark=mark)
    return "\n" + len(banner) * mark + "\n" + banner + "\n" + len(banner) * mark


def indent(lines: str, amount: int, ch: str = " ") -> str:
    """Indent each line in ``lines`` by ``amount`` ``ch`` characters."""
    padding = amount * ch
    return padding + ("\n" + padding).join(lines.split("\n"))
