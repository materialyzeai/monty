"""Pretty printing functions."""

from __future__ import annotations

import sys
from io import StringIO
from json import JSONEncoder, loads
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TextIO
    from collections.abc import Callable


def pprint_table(
    table: list[list], out: TextIO = sys.stdout, rstrip: bool = False
) -> None:
    """Prints out a table of data, padded for alignment
    Each row must have the same number of columns.

    Args:
        table: The table to print. A list of lists.
        out: Output stream (file-like object)
        rstrip: if True, trailing withespaces are removed from the entries.
    """

    def max_width_col(table: list[list], col_idx: int) -> int:
        """Get the maximum width of the given column index."""
        return max(len(row[col_idx]) for row in table)

    if rstrip:
        for row_idx, row in enumerate(table):
            table[row_idx] = [c.rstrip() for c in row]

    ncols = len(table[0])
    col_paddings = [max_width_col(table, i) for i in range(ncols)]

    for row in table:
        # left col
        out.write(row[0].ljust(col_paddings[0] + 1))
        # rest of the cols
        for i in range(1, len(row)):
            col = row[i].rjust(col_paddings[i] + 2)
            out.write(col)
        out.write("\n")


def draw_tree(node, child_iter=lambda n: n.children, text_str=str):
    """Args:
        node: the root of the tree to be drawn,
        child_iter: function that when called with a node, returns an iterable
            over all its children
        text_str: turns a node into the text to be displayed in the tree.

    The default implementations of these two arguments retrieve the children
    by accessing node.children and simply use str(node) to convert a node to a
    string. The resulting tree is drawn into a buffer and returned as a string.

    Based on https://pypi.python.org/pypi/asciitree/
    """
    return _draw_tree(node, "", child_iter, text_str)


def _draw_tree(node, prefix: str, child_iter: Callable, text_str: Callable):
    buf = StringIO()

    children = list(child_iter(node))

    # check if root node
    if prefix:
        buf.write(prefix[:-3])
        buf.write("  +--")
    buf.write(text_str(node))
    buf.write("\n")

    for index, child in enumerate(children):
        sub_prefix = prefix + "   " if index + 1 == len(children) else prefix + "  |"

        buf.write(_draw_tree(child, sub_prefix, child_iter, text_str))

    return buf.getvalue()


class DisplayEcoder(JSONEncoder):
    """Help convert dicts and objects to a format that can be displayed in notebooks."""

    def default(self, o):
        """Try different ways of converting the present object for displaying."""
        try:
            return o.as_dict()
        except Exception:
            pass

        try:
            return o.__dict__
        except Exception:
            pass

        try:
            return str(o)
        except Exception:
            pass

        return None


def pprint_json(data):
    """Display a tree-like object in a jupyter notebook.
    Allows for collapsible interactive interaction with data.

    Args:
        data: a dictionary or object

    Based on:
    https://gist.github.com/jmmshn/d37d5a1be80a6da11f901675f195ca22

    """
    from IPython.display import JSON, display  # pylint: disable=C0415

    display(JSON(loads(DisplayEcoder().encode(data))))
