"""
Path based methods, e.g., which, zpath, etc.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from monty.fnmatch import WildCard
from monty.string import list_strings

if TYPE_CHECKING:
    from typing import Callable, Literal, Optional, Union

    from monty.shutil import PathLike


def zpath(filename: PathLike) -> str:
    """
    Returns an existing (zipped or unzipped) file path given the unzipped
    version. If no path exists, returns the filename unmodified.

    Args:
        filename: filename without zip extension

    Returns:
        str: filename with a zip extension (unless an unzipped version exists).
            If filename is not found, the same filename is returned unchanged.
    """
    filename = str(filename)  # ensure we work with strings
    exts = ("", ".gz", ".GZ", ".bz2", ".BZ2", ".z", ".Z")
    for ext in exts:
        filename = filename.removesuffix(ext)

    for ext in exts:
        zfilename = f"{filename}{ext}"
        if os.path.exists(zfilename):
            return zfilename
    return filename


def find_exts(
    top: str,
    exts: Union[str, list[str]],
    exclude_dirs: Optional[str] = None,
    include_dirs: Optional[str] = None,
    match_mode: Literal["basename", "abspath"] = "basename",
) -> list[str]:
    """
    Find all files with the extension listed in `exts` that are located within
    the directory tree rooted at `top` (including top itself, but excluding
    '.' and '..')

    Args:
        top (str): Root directory
        exts (str or list of strings): List of extensions.
        exclude_dirs (str): Wildcards used to exclude particular directories.
            Can be concatenated via `|`
        include_dirs (str): Wildcards used to select particular directories.
            `include_dirs` and `exclude_dirs` are mutually exclusive
        match_mode (str): "basename" if  match should be done on the basename.
            "abspath" for absolute path.

    Returns:
        list[str]: Absolute paths of the files.

    Examples:
        # Find all pdf and ps files starting from the current directory.
        find_exts(".", ("pdf", "ps"))

        # Find all pdf files, exclude hidden directories and dirs whose name
        # starts with `_`
        find_exts(".", "pdf", exclude_dirs="_*|.*")

        # Find all ps files, in the directories whose basename starts with
        # output.
        find_exts(".", "ps", include_dirs="output*"))
    """
    exts = list_strings(exts)

    # Handle file!
    if os.path.isfile(top):
        return [os.path.abspath(top)] if any(top.endswith(ext) for ext in exts) else []

    # Build shell-style wildcards.
    if exclude_dirs is not None:
        _exclude_dirs: WildCard = WildCard(exclude_dirs)

    if include_dirs is not None:
        _include_dirs: WildCard = WildCard(include_dirs)

    mangle_functions: dict[str, Callable[..., str]] = {
        "basename": os.path.basename,
        "abspath": os.path.abspath,
    }
    mangle: Callable[..., str] = mangle_functions[match_mode]

    # Assume directory
    paths = []
    for dirpath, _dirnames, filenames in os.walk(top):
        dirpath = os.path.abspath(dirpath)

        if exclude_dirs and _exclude_dirs.match(mangle(dirpath)):
            continue
        if include_dirs and not _include_dirs.match(mangle(dirpath)):
            continue

        for filename in filenames:
            if any(filename.endswith(ext) for ext in exts):
                paths.append(os.path.join(dirpath, filename))

    return paths
