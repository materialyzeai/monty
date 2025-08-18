from __future__ import annotations

import os
import platform
import shutil

import pytest

from monty.tempfile import ScratchDir

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_files")


class TestScratchDir:
    def setup_method(self):
        self.cwd = os.getcwd()
        os.chdir(TEST_DIR)
        self.scratch_root = os.path.join(TEST_DIR, "..", "..", "tempscratch")
        os.mkdir(self.scratch_root)

    def test_with_copy(self):
        # We write a pre-scratch file.
        with open("pre_scratch_text", "w", encoding="utf-8") as f:
            f.write("write")

        orig_cwd = os.getcwd()

        # Expect a warning on exit due to newer file in CWD than in temp
        with (
            pytest.warns(RuntimeWarning, match="files newer in CWD"),
            ScratchDir(
                self.scratch_root,
                copy_from_current_on_enter=True,
                copy_to_current_on_exit=True,
            ) as d,
        ):
            with open("scratch_text", "w", encoding="utf-8") as f:
                f.write("write")
            files = os.listdir(d)
            assert "scratch_text" in files
            assert "empty_file.txt" in files
            assert "pre_scratch_text" in files

            # Make a file in the ORIGINAL CWD newer than the copy in temp.
            with open(
                os.path.join(orig_cwd, "empty_file.txt"), "a", encoding="utf-8"
            ) as f:
                f.write("hello\n")

            # We remove the pre-scratch file.
            os.remove("pre_scratch_text")

        # Make sure the tempdir is deleted.
        assert not os.path.exists(d)
        files = os.listdir(".")
        assert "scratch_text" in files
        os.remove("scratch_text")

        os.remove("pre_scratch_text")

    def test_with_copy_gzip(self):
        # We write a pre-scratch file.
        with open("pre_scratch_text", "w", encoding="utf-8") as f:
            f.write("write")
        init_gz_files = [f for f in os.listdir(os.getcwd()) if f.endswith(".gz")]
        with pytest.warns(match="Both 3000_lines.txt and 3000_lines.txt.gz exist."):
            with (
                ScratchDir(
                    self.scratch_root,
                    copy_from_current_on_enter=True,
                    copy_to_current_on_exit=True,
                    gzip_on_exit=True,
                ),
                open("scratch_text", "w", encoding="utf-8") as f,
            ):
                f.write("write")
        files = os.listdir(os.getcwd())

        # Make sure the scratch_text.gz exists
        assert "scratch_text.gz" in files
        for f in files:
            if f.endswith(".gz") and f not in init_gz_files:
                os.remove(f)
        os.remove("pre_scratch_text")
        os.remove("scratch_text")

    def test_no_copy(self):
        with ScratchDir(
            self.scratch_root,
            copy_from_current_on_enter=False,
            copy_to_current_on_exit=False,
        ) as d:
            with open("scratch_text", "w", encoding="utf-8") as f:
                f.write("write")
            files = os.listdir(d)
            assert "scratch_text" in files
            assert "empty_file.txt" not in files

        # Make sure the tempdir is deleted.
        assert not os.path.exists(d)
        files = os.listdir(".")
        assert "scratch_text" not in files

    def test_symlink(self):
        if platform.system() != "Windows":
            orig_cwd = os.getcwd()  # where the symlink will be created

            with ScratchDir(
                self.scratch_root,
                copy_from_current_on_enter=False,
                copy_to_current_on_exit=False,
                create_symbolic_link=True,
            ) as d:
                with open("scratch_text", "w", encoding="utf-8") as f:
                    f.write("write")

                files = os.listdir(d)
                assert "scratch_text" in files
                assert "empty_file.txt" not in files

                # Check symlink
                link_path = os.path.join(orig_cwd, ScratchDir.SCR_LINK)
                assert os.path.islink(link_path)

                assert os.readlink(link_path) == d

            # Make sure the tempdir is deleted.
            assert not os.path.exists(d)
            files = os.listdir(".")
            assert "scratch_text" not in files

            # Make sure the symlink is removed
            assert not os.path.islink(ScratchDir.SCR_LINK)

    def test_bad_rootpath(self):
        # rootpath doesn't exist
        assert not os.path.isdir("non_existent_root")
        with pytest.warns(RuntimeWarning, match="pass through"):
            with ScratchDir("non_existent_root") as d:
                assert d == TEST_DIR

        # rootpath isn't a directory
        assert os.path.isfile("empty_file.txt")
        with pytest.warns(RuntimeWarning, match="pass through"):
            with ScratchDir("empty_file.txt") as d:
                assert d == TEST_DIR

    def test_rootpath_as_none(self):
        orig_cwd = os.getcwd()
        scratch_file_name = "scratch_text"

        with ScratchDir(
            rootpath=None,
        ) as d:
            assert d == orig_cwd
            assert os.getcwd() == orig_cwd

            with open(scratch_file_name, "w", encoding="utf-8") as f:
                f.write("write")

        assert os.path.exists(scratch_file_name)
        os.remove(scratch_file_name)

    def teardown_method(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.scratch_root)
