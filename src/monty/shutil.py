"""Copying and zipping utilities. Works on directories mostly."""

from __future__ import annotations

import os
import shutil
import warnings
from gzip import GzipFile
from pathlib import Path
from typing import TYPE_CHECKING, Union

from monty.io import zopen

if TYPE_CHECKING:
    from typing import Literal, Optional, TypeAlias

PathLike: TypeAlias = Union[str, Path]


def copy_r(src: PathLike, dst: PathLike) -> None:
    """
    Deprecated: please use `shutil.copytree(src, dst, dirs_exist_ok=True)`,
    use the `symlinks` arg to control whether you want to dereference symlinks.

    Implements a recursive copy function similar to Unix's "cp -r" command.
    Surprisingly, python does not have a real equivalent. shutil.copytree
    only works if the destination directory is not present.

    Args:
        src (PathLike): Source folder to copy.
        dst (PathLike): Destination folder.
    """
    # TODO: remove after 2027-01-01
    warnings.warn(
        "please use `shutil.copytree(src, dst, dirs_exist_ok=True)`",
        DeprecationWarning,
        stacklevel=2,
    )
    shutil.copytree(src, dst, dirs_exist_ok=True)


def gzip_dir(path: PathLike, compresslevel: int = 6) -> None:
    """
    Gzips all files in a directory. Note that this is different from
    shutil.make_archive, which creates a tar archive. The aim of this method
    is to create gzipped files that can still be read using common Unix-style
    commands like zless or zcat.

    Args:
        path (PathLike): Path to directory.
        compresslevel (int): Level of compression, 1-9. 9 is default for
            GzipFile, 6 is default for gzip.
    """
    for root, _, files in os.walk(Path(path)):
        for f in files:
            full_f = Path(root, f).resolve()
            if Path(f).suffix.lower() != ".gz" and not full_f.is_dir():
                if os.path.exists(f"{full_f}.gz"):
                    warnings.warn(f"Both {f} and {f}.gz exist.", stacklevel=2)
                    continue

                with (
                    open(full_f, "rb") as f_in,
                    GzipFile(
                        f"{full_f}.gz", "wb", compresslevel=compresslevel
                    ) as f_out,
                ):
                    shutil.copyfileobj(f_in, f_out)
                shutil.copystat(full_f, f"{full_f}.gz")
                os.remove(full_f)


def compress_file(
    filepath: PathLike,
    compression: Literal["gz", "bz2"] = "gz",
    target_dir: Optional[PathLike] = None,
) -> None:
    """
    Compresses a file with the correct extension. Functions like standard
    Unix command line gzip and bzip2 in the sense that the original
    uncompressed files are not retained.

    Args:
        filepath (PathLike): Path to file.
        compression (str): A compression mode. Valid options are "gz" or
            "bz2". Defaults to "gz".
        target_dir (PathLike): An optional target dir where the result compressed
            file would be stored. Defaults to None for in-place compression.
    """
    filepath = Path(filepath)
    target_dir = Path(target_dir) if target_dir is not None else None

    if compression not in {"gz", "bz2"}:
        raise ValueError("Supported compression formats are 'gz' and 'bz2'.")

    if filepath.suffix.lower() != f".{compression}" and not filepath.is_symlink():
        if target_dir is not None:
            os.makedirs(target_dir, exist_ok=True)
            compressed_file: PathLike = target_dir / f"{filepath.name}.{compression}"

        else:
            compressed_file = f"{str(filepath)}.{compression}"

        with open(filepath, "rb") as f_in, zopen(compressed_file, mode="wb") as f_out:
            f_out.writelines(f_in)

        os.remove(filepath)


def compress_dir(path: PathLike, compression: Literal["gz", "bz2"] = "gz") -> None:
    """
    Recursively compresses all files in a directory. Note that this
    compresses all files singly, i.e., it does not create a tar archive. For
    that, just use Python tarfile class.

    Args:
        path (PathLike): Path to parent directory.
        compression (str): A compression mode. Valid options are "gz" or
            "bz2". Defaults to gz.
    """
    path = Path(path)
    for parent, _, files in os.walk(path):
        for f in files:
            compress_file(Path(parent, f), compression=compression)

    return


def decompress_file(
    filepath: PathLike, target_dir: Optional[PathLike] = None
) -> str | None:
    """
    Decompresses a file with the correct extension. Automatically detects
    gz, bz2 or z extension.

    Args:
        filepath (PathLike): Path to file.
        target_dir (PathLike): An optional target dir where the result decompressed
            file would be stored. Defaults to None for in-place decompression.

    Returns:
        str | None: The decompressed file path, None if no operation.
    """
    filepath = Path(filepath)
    target_dir = Path(target_dir) if target_dir is not None else None
    file_ext = filepath.suffix

    if file_ext.lower() in {".bz2", ".gz", ".z"} and filepath.is_file():
        if target_dir is not None:
            os.makedirs(target_dir, exist_ok=True)
            decompressed_file: PathLike = target_dir / filepath.name.removesuffix(
                file_ext
            )
        else:
            decompressed_file = str(filepath).removesuffix(file_ext)

        with zopen(filepath, mode="rb") as f_in, open(decompressed_file, "wb") as f_out:
            f_out.writelines(f_in)

        os.remove(filepath)

        return str(decompressed_file)
    return None


def decompress_dir(path: PathLike) -> None:
    """
    Recursively decompresses all files in a directory.

    Args:
        path (PathLike): Path to parent directory.
    """
    path = Path(path)
    for parent, _, files in os.walk(path):
        for f in files:
            decompress_file(Path(parent, f))


def remove(path: PathLike, follow_symlink: bool = False) -> None:
    """
    Implements a remove function that will delete files, folder trees and
    symlink trees.

    1.) Remove a file
    2.) Remove a symlink and follow into with a recursive rm if follow_symlink
    3.) Remove directory with rmtree

    Args:
        path (PathLike): path to remove
        follow_symlink(bool): follow symlinks and removes whatever is in them
    """
    path = Path(path)
    if path.is_file():
        os.remove(path)
    elif path.is_symlink():
        if follow_symlink:
            remove(os.readlink(path))
        Path.unlink(path)
    else:
        shutil.rmtree(path)
