"""Useful additional functions to help get information about live objects."""

from __future__ import annotations

import os
import sys
from inspect import currentframe, getframeinfo, getmodule
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal


def all_subclasses(cls: type) -> list[type]:
    """Given a class ``cls``, this function returns a list with all subclasses,
    subclasses of subclasses, and so on.

    Uses an explicit stack with ``set``-based de-duplication so a class that
    appears under multiple base classes (diamond inheritance) is not reported
    more than once and recursion depth is bounded.
    """
    seen: set[type] = set()
    out: list[type] = []
    stack: list[type] = list(cls.__subclasses__())
    while stack:
        sub = stack.pop()
        if sub in seen:
            continue
        seen.add(sub)
        out.append(sub)
        stack.extend(sub.__subclasses__())
    return out


def find_top_pyfile() -> str:
    """This function inspects the Cpython frame to find the path of the script."""
    frame = currentframe()
    if frame is None:
        raise RuntimeError("Could not obtain current frame.")
    while frame.f_back is not None:
        frame = frame.f_back
    finfo = getframeinfo(frame)
    return os.path.abspath(finfo.filename)


def caller_name(skip: Literal[1, 2] = 2) -> str:
    """Get a name of a caller in the format module.class.method.

    ``skip`` specifies how many levels of stack to skip while getting caller
    name. skip=1 means "who calls me", skip=2 "who calls my caller" etc.

    An empty string is returned if skipped levels exceed stack height.

    Implementation note: this used to call ``inspect.stack()``, which builds a
    full ``FrameInfo`` (including source lines) for *every* frame in the call
    stack — orders of magnitude more work than necessary. We walk the frame
    chain manually with ``sys._getframe`` and only inspect the one frame we
    care about.

    Taken from:

        https://gist.github.com/techtonik/2151727

    Public Domain, i.e. feel free to copy/paste
    """
    # ``sys._getframe(0)`` is this frame (caller_name) — same indexing as
    # the original ``inspect.stack()[skip]`` implementation.
    try:
        parentframe = sys._getframe(skip)
    except ValueError:
        return ""

    name: list[str] = []

    # ``modname`` can be None when frame is executed directly in console
    if module := getmodule(parentframe):
        name.append(module.__name__)

    # detect classname
    if "self" in parentframe.f_locals:
        # I don't know any way to detect call from the object method
        # XXX: there seems to be no way to detect static method call - it will
        #      be just a function call
        name.append(parentframe.f_locals["self"].__class__.__name__)

    codename = parentframe.f_code.co_name
    if codename != "<module>":  # top level usually
        name.append(codename)  # function or a method
    del parentframe

    return ".".join(name)
