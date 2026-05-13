"""Copyright (c) 2008-2011 Volvox Development Team.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
# Author: Konstantin Lepa <konstantin.lepa@gmail.com>

ANSII Color formatting for output in terminal.
"""

from __future__ import annotations

import contextlib
import os

with contextlib.suppress(Exception):
    import curses
    import fcntl
    import struct
    import termios


__all__ = ["colored", "cprint"]

VERSION = (1, 1, 0)

ATTRIBUTES = {
    "bold": 1,
    "dark": 2,
    "underline": 4,
    "blink": 5,
    "reverse": 7,
    "concealed": 8,
}

HIGHLIGHTS = {
    "on_grey": 40,
    "on_red": 41,
    "on_green": 42,
    "on_yellow": 43,
    "on_blue": 44,
    "on_magenta": 45,
    "on_cyan": 46,
    "on_white": 47,
}

COLORS = {
    "grey": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "white": 37,
}

RESET = "\033[0m"

__ISON = True


def enable(true_false: bool) -> None:
    """Enable/Disable ANSII Color formatting."""
    global __ISON
    __ISON = true_false


def ison() -> bool:
    """True if ANSII Color formatting is activated."""
    return __ISON


def stream_has_colours(stream: object) -> bool:
    """True if stream supports colours. Python cookbook, #475186."""
    if not hasattr(stream, "isatty"):
        return False

    if not stream.isatty():
        return False  # auto color only on TTYs
    try:
        curses.setupterm()
        return curses.tigetnum("colors") > 2
    except Exception:
        return False  # guess false in case of error


def colored(
    text: str,
    color: str = "",
    on_color: str = "",
    attrs: list[str] | None = None,
) -> str:
    """Colorize text.

    Available text colors:
        red, green, yellow, blue, magenta, cyan, white.

    Available text highlights:
        on_red, on_green, on_yellow, on_blue, on_magenta, on_cyan, on_white.

    Available attributes:
        bold, dark, underline, blink, reverse, concealed.

    Examples:
        colored('Hello, World!', 'red', 'on_grey', ['blue', 'blink'])
        colored('Hello, World!', 'green')
    """
    if __ISON and os.getenv("ANSI_COLORS_DISABLED") is None:
        fmt_str = "\033[%dm%s"
        if color:
            text = fmt_str % (COLORS[color], text)

        if on_color:
            text = fmt_str % (HIGHLIGHTS[on_color], text)

        if attrs:
            for attr in attrs:
                text = fmt_str % (ATTRIBUTES[attr], text)

        text += RESET
    return text


def cprint(
    text: str,
    color: str = "",
    on_color: str = "",
    attrs: list[str] | None = None,
    **kwargs,
) -> None:
    """Print colorize text.

    It accepts arguments of print function.
    """
    print((colored(text, color, on_color, attrs)), **kwargs)


def colored_map(text: str, cmap: dict) -> str:
    """Return colorized text. cmap is a dict mapping tokens to color options.

    colored_key("foo bar", {bar: "green"})
    colored_key("foo bar", {bar: {"color": "green", "on_color": "on_red"}})
    """
    if not __ISON:
        return text
    for key, v in cmap.items():
        if isinstance(v, dict):
            text = text.replace(key, colored(key, **v))
        else:
            text = text.replace(key, colored(key, color=v))
    return text


def cprint_map(text: str, cmap: dict, **kwargs) -> None:
    """Print colorize text.
    cmap is a dict mapping keys to color options.
    kwargs are passed to print function.

    Examples:
        cprint_map("Hello world", {"Hello": "red"})
    """
    print(colored_map(text, cmap), **kwargs)


def get_terminal_size():
    """Return the size of the terminal as (nrow, ncols).

    Based on:

        http://stackoverflow.com/questions/566746/how-to-get-console-window-
        width-in-python
    """
    with contextlib.suppress(Exception):
        rc = os.popen("stty size", "r").read().split()
        return int(rc[0]), int(rc[1])

    env = os.environ

    def ioctl_GWINSZ(fd):
        try:
            return struct.unpack("hh", fcntl.ioctl(fd, termios.TIOCGWINSZ, "1234"))
        except Exception:
            return None

    rc = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)

    if not rc:
        with contextlib.suppress(Exception):
            fd = os.open(os.ctermid(), os.O_RDONLY)
            rc = ioctl_GWINSZ(fd)
            os.close(fd)

    if not rc:
        rc = (env.get("LINES", 25), env.get("COLUMNS", 80))

    return int(rc[0]), int(rc[1])
