"""
Useful additional string functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Any, Iterable, Union


def remove_non_ascii(s: str) -> str:
    """
    Remove non-ascii characters in a file. Needed when support for non-ASCII
    is not available.

    Args:
        s (str): Input string

    Returns:
        String with all non-ascii characters removed.
    """
    return "".join(i for i in s if ord(i) < 128)


def is_string(s: Any) -> bool:
    """True if s behaves like a string (duck typing test)."""
    try:
        s + " "
        return True

    except TypeError:
        return False


def list_strings(arg: Union[str, Iterable[str]]) -> list[str]:
    """
    Always return a list of strings, given a string or list of strings as
    input.

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
    if is_string(arg):
        return [cast(str, arg)]

    return [cast(str, s) for s in arg]


def marquee(text: str = "", width: int = 78, mark: str = "*") -> str:
    """
    Return the input string centered in a 'marquee'.

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
    """
    Returns a string in a box

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
    """
    Args:
        s: String
        width: Width of banner. Defaults to 78.
        mark: The mark used to create the banner.

    Returns:
        Banner string.
    """
    banner = marquee(s, width=width, mark=mark)
    return "\n" + len(banner) * mark + "\n" + banner + "\n" + len(banner) * mark


def indent(lines: str, amount: int, ch: str = " ") -> str:
    """
    Indent the lines in a string by padding each one with proper number of pad
    characters
    """
    padding = amount * ch
    return padding + ("\n" + padding).join(lines.split("\n"))
