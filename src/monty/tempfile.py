"""
Temporary directory and file creation utilities.
"""

from __future__ import annotations

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
    """
    Notes:
        With effect from Python 3.2, tempfile.TemporaryDirectory already
        implements much of the functionality of ScratchDir. However, it does
        not provide options for copying of files to and from (though it is
        possible to do this with other methods provided by shutil).

    Creates a "with" context manager that automatically handles creation of
    temporary directories (utilizing Python's build in temp directory
    functions) and cleanup when done. This improves on Python's built in
    functions by allowing for truly temporary workspace that are deleted
    when it is done. The way it works is as follows:

    1. Create a temp dir in specified root path.
    2. Optionally copy input files from current directory to temp dir.
    3. Change to temp dir.
    4. User performs specified operations.
    5. Optionally copy generated output files back to original directory.
    6. Change back to original directory.
    7. Delete temp dir.
    """

    SCR_LINK: ClassVar[str] = "scratch_link"

    def __init__(
        self,
        rootpath: Union[PathLike, None],
        create_symbolic_link: bool = False,
        copy_from_current_on_enter: bool = False,
        copy_to_current_on_exit: bool = False,
        gzip_on_exit: bool = False,
    ) -> None:
        """
        Initializes scratch directory given a **root** path. There is no need
        to try to create unique directory names. The code will generate a
        temporary sub directory in the rootpath. The way to use this is using a
        with context manager. Example::

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
        """
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

                # Timestamp check
                def get_files(root: PathLike) -> set[str]:
                    paths: set[str] = set()
                    for dirpath, _, filenames in os.walk(root):
                        for fn in filenames:
                            abs_path = os.path.join(dirpath, fn)
                            rel_path = os.path.relpath(abs_path, root)
                            paths.add(rel_path)
                    return paths

                def get_modif_times(
                    root: PathLike,
                    rel_paths: set[str],
                ) -> dict[str, float]:
                    out: dict[str, float] = {}
                    for rel in rel_paths:
                        try:
                            out[rel] = os.path.getmtime(os.path.join(root, rel))
                        except FileNotFoundError:
                            # File may have been removed between listing and stat
                            pass
                    return out

                common_paths = get_files(self.tempdir) & get_files(self.cwd)
                temp_mtimes = get_modif_times(self.tempdir, common_paths)
                cwd_mtimes = get_modif_times(self.cwd, common_paths)

                newer_in_cwd = [
                    rel
                    for rel in common_paths
                    if rel in temp_mtimes
                    and rel in cwd_mtimes
                    and cwd_mtimes[rel] > temp_mtimes[rel]
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
