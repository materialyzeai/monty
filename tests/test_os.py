from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from monty.os import cd, makedirs_p
from monty.os.path import find_exts, zpath

if TYPE_CHECKING:
    from pathlib import Path

MODULE_DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(MODULE_DIR, "test_files")


class TestPath:
    def test_zpath_str(self, tmp_path: Path):
        tmp_gz = tmp_path / "tmp.gz"
        tmp_gz.touch()
        ret_path = zpath(str(tmp_gz))
        assert isinstance(ret_path, str)
        assert ret_path == str(tmp_gz)

        tmp_not_bz2 = tmp_path / "tmp_not_bz2"
        tmp_not_bz2.touch()

        ret_path = zpath(f"{tmp_not_bz2}.bz2")
        assert ret_path == str(tmp_not_bz2)
        assert isinstance(ret_path, str)

    def test_zpath_path(self, tmp_path: Path):
        # Test with Path input
        tmp_gz = tmp_path / "tmp.gz"
        tmp_gz.touch()
        ret_path = zpath(tmp_gz)
        assert ret_path == str(tmp_gz)
        assert isinstance(ret_path, str)

    def test_zpath_multiple_extensions(self, tmp_path: Path):
        exts = ["", ".gz", ".GZ", ".bz2", ".BZ2", ".z", ".Z"]
        for ext in exts:
            tmp_file = tmp_path / f"tmp{ext}"
            # create files with all supported compression extensions
            tmp_file.touch()

        # zpath should return the file without compression extension
        ret_path = zpath(tmp_path / "tmp")
        assert ret_path == str(tmp_path / "tmp")
        assert isinstance(ret_path, str)

        (tmp_path / "tmp").unlink()  # Remove the uncompressed file
        ret_path = zpath(tmp_path / "tmp")
        assert ret_path == str(tmp_path / "tmp.gz")  # should find .gz first now

    def test_zpath_nonexistent_file(self, tmp_path: Path):
        # should return path as is for non-existent file
        nonexistent = tmp_path / "nonexistent.txt"
        ret_path = zpath(nonexistent)
        assert ret_path == str(nonexistent)
        ret_path = zpath(f"{nonexistent}.bz2")
        assert ret_path == str(nonexistent)

    def test_find_exts(self):
        assert len(find_exts(MODULE_DIR, "py")) >= 18
        assert len(find_exts(MODULE_DIR, "bz2")) == 2
        n_bz2_excl_tests = len(find_exts(MODULE_DIR, "bz2", exclude_dirs="test_files"))
        assert n_bz2_excl_tests == 0
        n_bz2_w_tests = find_exts(MODULE_DIR, "bz2", include_dirs="test_files")
        assert len(n_bz2_w_tests) == 2


class TestCd:
    def test_cd(self):
        with cd(TEST_DIR):
            assert os.path.exists("empty_file.txt")
        assert not os.path.exists("empty_file.txt")

    def test_cd_exception(self):
        with cd(TEST_DIR):
            assert os.path.exists("empty_file.txt")
        assert not os.path.exists("empty_file.txt")


class TestMakedirs_p:
    def setup_method(self):
        self.test_dir_path = os.path.join(TEST_DIR, "test_dir")

    def test_makedirs_p(self):
        makedirs_p(self.test_dir_path)
        assert os.path.exists(self.test_dir_path)
        makedirs_p(self.test_dir_path)
        with pytest.raises(OSError, match="exists"):
            makedirs_p(os.path.join(TEST_DIR, "3000_lines.txt"))

    def teardown_method(self):
        os.rmdir(self.test_dir_path)
