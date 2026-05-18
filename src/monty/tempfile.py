"""Temporary directory and file creation utilities."""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
import warnings
from typing import TYPE_CHECKING

from monty.shutil import gzip_dir, remove

if TYPE_CHECKING:
    from typing import ClassVar, Union

    from monty.shutil import PathLike


class ScratchDir:
    """Context manager that creates and cleans up a temporary working directory.

    Creates a "with" context manager that automatically handles creation of
    temporary directories (utilizing Python's built-in temp directory
    functions) and cleanup when done. This improves on Python's built-in
    functions by allowing for truly temporary workspaces that are deleted
    when it is done. The way it works is as follows:

    1. Create a temp dir in specified root path.
    2. Optionally copy input files from current directory to temp dir.
    3. Change to temp dir.
    4. User performs specified operations.
    5. Optionally copy generated output files back to original directory.
    6. Change back to original directory.
    7. Delete temp dir.

    Note:
        From Python 3.2 on, ``tempfile.TemporaryDirectory`` implements much
        of the functionality of ScratchDir. However, it does not provide
        options for copying of files to and from (though it is possible to
        do this with other methods provided by shutil).

    """

    SCR_LINK: ClassVar[str] = "scratch_link"

    def __init__(
        self,
        rootpath: PathLike | None,
        create_symbolic_link: bool = False,
        copy_from_current_on_enter: bool = False,
        copy_to_current_on_exit: bool = False,
        gzip_on_exit: bool = False,
        delete_removed_files: bool | None = None,
    ) -> None:
        """Initialize scratch directory given a **root** path.

        There is no need to try to create unique directory names. The code
        will generate a temporary sub directory in the rootpath. The way to
        use this is using a with context manager. Example::

            with ScratchDir("/scratch"):
                do_something()

        If the root path does not exist or is None, this will function as a
        simple pass through, i.e., nothing happens.

        Args:
            rootpath (str/Path): Path in which to create temp subdirectories.
                If this is None or not a directory, no temp directories will be
                created and this will just be a simple pass through.
            create_symbolic_link (bool): Whether to create a symbolic link in
                the current working directory to the scratch directory
                created.
            copy_from_current_on_enter (bool): Whether to copy all files from
                the current directory (recursively) to the temp dir at the
                start, e.g., if input files are needed for performing some
                actions. Defaults to False.
            copy_to_current_on_exit (bool): Whether to copy files from the
                scratch to the current directory (recursively) at the end. E
                .g., if output files are generated during the operation.
                Defaults to False.
            gzip_on_exit (bool): Whether to gzip the files generated in the
                ScratchDir before copying them back.
                Defaults to False.
            delete_removed_files (DEPRECATED): It now has no effect
                and will be removed in 2027-01-01.

        """
        if delete_removed_files is not None:
            warnings.warn(
                "The 'delete_removed_files' argument is deprecated and has no effect. "
                "It will be removed in 2027-01-01.",
                DeprecationWarning,
                stacklevel=2,
            )

        self.cwd: str = os.getcwd()
        self.rootpath: str | None = (
            None if rootpath is None else os.path.abspath(rootpath)
        )
        self.pass_through: bool = self.rootpath is None or not os.path.isdir(
            self.rootpath
        )
        if self.rootpath is not None and not os.path.isdir(self.rootpath):
            warnings.warn(
                f"rootpath {self.rootpath} doesn't exist and is not directory, would just pass through",
                RuntimeWarning,
                stacklevel=2,
            )

        self.create_symbolic_link: bool = create_symbolic_link
        self.enter_copy: bool = copy_from_current_on_enter
        self.exit_copy: bool = copy_to_current_on_exit
        self.gzip_on_exit: bool = gzip_on_exit

    def __enter__(self) -> str:
        tempdir: str = self.cwd
        if not self.pass_through:
            tempdir = tempfile.mkdtemp(dir=self.rootpath)
            self.tempdir = os.path.abspath(tempdir)
            if self.enter_copy:
                shutil.copytree(self.cwd, tempdir, dirs_exist_ok=True)
            if self.create_symbolic_link:
                os.symlink(tempdir, ScratchDir.SCR_LINK)
            os.chdir(tempdir)
        return tempdir

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self.pass_through:
            if self.exit_copy:
                # gzip files
                if self.gzip_on_exit:
                    gzip_dir(self.tempdir)

                def walk_with_mtimes(root: PathLike) -> dict[str, float]:
                    """Single-pass scandir walk: build {relpath -> mtime}.

                    ``DirEntry.stat()`` reuses the ``stat`` info collected by
                    the directory iterator on most platforms, avoiding the
                    extra syscall pair that ``os.walk`` + ``os.path.getmtime``
                    would incur.
                    """
                    out: dict[str, float] = {}
                    root_str = os.fspath(root)
                    stack: list[str] = [root_str]
                    while stack:
                        d = stack.pop()
                        try:
                            with os.scandir(d) as it:
                                for entry in it:
                                    if entry.is_dir(follow_symlinks=False):
                                        stack.append(entry.path)
                                    else:
                                        with contextlib.suppress(FileNotFoundError):
                                            out[
                                                os.path.relpath(entry.path, root_str)
                                            ] = entry.stat().st_mtime
                        except FileNotFoundError:
                            continue
                    return out

                temp_mtimes = walk_with_mtimes(self.tempdir)
                cwd_mtimes = walk_with_mtimes(self.cwd)

                newer_in_cwd = [
                    rel
                    for rel, t in cwd_mtimes.items()
                    if rel in temp_mtimes and t > temp_mtimes[rel]
                ]

                if newer_in_cwd:
                    warnings.warn(
                        "ScratchDir: Detected files newer in CWD than tempdir; "
                        f"copy-back would overwrite: {', '.join(newer_in_cwd)}",
                        RuntimeWarning,
                        stacklevel=2,
                    )

                # copy files over
                shutil.copytree(self.tempdir, self.cwd, dirs_exist_ok=True)

            os.chdir(self.cwd)
            remove(self.tempdir)
            if self.create_symbolic_link and os.path.islink(ScratchDir.SCR_LINK):
                os.remove(ScratchDir.SCR_LINK)
