from __future__ import annotations

import os
import platform
import shutil
import tempfile
from gzip import GzipFile
from pathlib import Path

import pytest

from monty.shutil import (
    compress_dir,
    compress_file,
    copy_r,
    decompress_dir,
    decompress_file,
    gzip_dir,
    remove,
)

TEST_DIR = os.path.join(os.path.dirname(__file__), "test_files")


class TestCopyR:
    def setup_method(self):
        os.mkdir(os.path.join(TEST_DIR, "cpr_src"))
        with open(
            os.path.join(TEST_DIR, "cpr_src", "test"), "w", encoding="utf-8"
        ) as f:
            f.write("what")
        os.mkdir(os.path.join(TEST_DIR, "cpr_src", "sub"))
        with open(
            os.path.join(TEST_DIR, "cpr_src", "sub", "testr"), "w", encoding="utf-8"
        ) as f:
            f.write("what2")
        if platform.system() != "Windows":
            os.symlink(
                os.path.join(TEST_DIR, "cpr_src", "test"),
                os.path.join(TEST_DIR, "cpr_src", "mysymlink"),
            )

    def test_recursive_copy_and_compress(self):
        with pytest.warns(DeprecationWarning, match="shutil.copytree"):
            copy_r(os.path.join(TEST_DIR, "cpr_src"), os.path.join(TEST_DIR, "cpr_dst"))
        assert os.path.exists(os.path.join(TEST_DIR, "cpr_dst", "test"))
        assert os.path.exists(os.path.join(TEST_DIR, "cpr_dst", "sub", "testr"))

        compress_dir(os.path.join(TEST_DIR, "cpr_src"))
        assert os.path.exists(os.path.join(TEST_DIR, "cpr_src", "test.gz"))
        assert os.path.exists(os.path.join(TEST_DIR, "cpr_src", "sub", "testr.gz"))

        decompress_dir(os.path.join(TEST_DIR, "cpr_src"))
        assert os.path.exists(os.path.join(TEST_DIR, "cpr_src", "test"))
        assert os.path.exists(os.path.join(TEST_DIR, "cpr_src", "sub", "testr"))
        with open(os.path.join(TEST_DIR, "cpr_src", "test"), encoding="utf-8") as f:
            txt = f.read()
            assert txt == "what"

    def test_pathlib(self):
        test_path = Path(TEST_DIR)
        with pytest.warns(DeprecationWarning, match="shutil.copytree"):
            copy_r(test_path / "cpr_src", test_path / "cpr_dst")
        assert (test_path / "cpr_dst" / "test").exists()
        assert (test_path / "cpr_dst" / "sub" / "testr").exists()

    def teardown_method(self):
        shutil.rmtree(os.path.join(TEST_DIR, "cpr_src"))
        shutil.rmtree(os.path.join(TEST_DIR, "cpr_dst"))


class TestCompressFileDir:
    def setup_method(self):
        with open(os.path.join(TEST_DIR, "tempfile"), "w", encoding="utf-8") as f:
            f.write("hello world")

    def test_compress_and_decompress_file(self):
        fname = os.path.join(TEST_DIR, "tempfile")

        for fmt in ["gz", "bz2"]:
            compress_file(fname, fmt)
            assert os.path.exists(fname + "." + fmt)
            assert not os.path.exists(fname)

            decompress_file(fname + "." + fmt)
            assert os.path.exists(fname)
            assert not os.path.exists(fname + "." + fmt)

            with open(fname, encoding="utf-8") as f:
                assert f.read() == "hello world"

        with pytest.raises(ValueError):
            compress_file("whatever", "badformat")

        # test decompress non-existent/non-compressed file
        assert decompress_file("non-existent") is None
        assert decompress_file("non-existent.gz") is None
        assert decompress_file("non-existent.bz2") is None

    def test_compress_and_decompress_with_target_dir(self):
        fname = os.path.join(TEST_DIR, "tempfile")
        target_dir = os.path.join(TEST_DIR, "temp_target_dir")

        for fmt in ["gz", "bz2"]:
            compress_file(fname, fmt, target_dir)
            compressed_file_path = os.path.join(
                target_dir, f"{os.path.basename(fname)}.{fmt}"
            )
            assert os.path.exists(compressed_file_path)
            assert not os.path.exists(fname)

            decompress_file(compressed_file_path, target_dir)
            decompressed_file_path = os.path.join(target_dir, os.path.basename(fname))
            assert os.path.exists(decompressed_file_path)
            assert not os.path.exists(compressed_file_path)

            # Reset temp file position
            shutil.move(decompressed_file_path, fname)
            shutil.rmtree(target_dir)

            with open(fname, encoding="utf-8") as f:
                assert f.read() == "hello world"

    def teardown_method(self):
        os.remove(os.path.join(TEST_DIR, "tempfile"))


class TestGzipDir:
    def setup_method(self):
        os.mkdir(os.path.join(TEST_DIR, "gzip_dir"))
        with open(
            os.path.join(TEST_DIR, "gzip_dir", "tempfile"), "w", encoding="utf-8"
        ) as f:
            f.write("what")

        self.mtime = os.path.getmtime(os.path.join(TEST_DIR, "gzip_dir", "tempfile"))

    def test_gzip_dir(self):
        full_f = os.path.join(TEST_DIR, "gzip_dir", "tempfile")
        gzip_dir(os.path.join(TEST_DIR, "gzip_dir"))

        assert os.path.exists(f"{full_f}.gz")
        assert not os.path.exists(full_f)

        with GzipFile(f"{full_f}.gz") as g:
            assert g.readline().decode("utf-8") == "what"

        assert os.path.getmtime(f"{full_f}.gz") == pytest.approx(self.mtime, 4)

    def test_gzip_dir_file_coexist(self):
        """Test case where both file and file.gz exist."""
        full_f = os.path.join(TEST_DIR, "gzip_dir", "temptestfile")
        gz_f = f"{full_f}.gz"

        # Create both the file and its gzipped version
        with open(full_f, "w", encoding="utf-8") as f:
            f.write("not gzipped")
        with GzipFile(gz_f, "wb") as g:
            g.write(b"gzipped")

        with pytest.warns(
            UserWarning, match="Both temptestfile and temptestfile.gz exist."
        ):
            gzip_dir(os.path.join(TEST_DIR, "gzip_dir"))

        # Verify contents of the files
        with open(full_f, "r", encoding="utf-8") as f:
            assert f.read() == "not gzipped"

        with GzipFile(gz_f, "rb") as g:
            assert g.read() == b"gzipped"

    def test_handle_sub_dirs(self):
        sub_dir = os.path.join(TEST_DIR, "gzip_dir", "sub_dir")
        sub_file = os.path.join(sub_dir, "new_tempfile")
        os.mkdir(sub_dir)
        with open(sub_file, "w", encoding="utf-8") as f:
            f.write("anotherwhat")

        gzip_dir(os.path.join(TEST_DIR, "gzip_dir"))

        assert os.path.exists(f"{sub_file}.gz")
        assert not os.path.exists(sub_file)

        with GzipFile(f"{sub_file}.gz") as g:
            assert g.readline().decode("utf-8") == "anotherwhat"

    def teardown_method(self):
        shutil.rmtree(os.path.join(TEST_DIR, "gzip_dir"))


class TestRemove:
    @pytest.mark.skipif(platform.system() == "Windows", reason="Skip on windows")
    def test_remove_file(self):
        tempdir = tempfile.mkdtemp(dir=TEST_DIR)
        tempf = tempfile.mkstemp(dir=tempdir)[1]
        remove(tempf)
        assert not os.path.isfile(tempf)
        shutil.rmtree(tempdir)

    @pytest.mark.skipif(platform.system() == "Windows", reason="Skip on windows")
    def test_remove_folder(self):
        tempdir = tempfile.mkdtemp(dir=TEST_DIR)
        remove(tempdir)
        assert not os.path.isdir(tempdir)

    @pytest.mark.skipif(platform.system() == "Windows", reason="Skip on windows")
    def test_remove_symlink(self):
        tempdir = tempfile.mkdtemp(dir=TEST_DIR)
        tempf = tempfile.mkstemp(dir=tempdir)[1]

        os.symlink(tempdir, os.path.join(TEST_DIR, "temp_link"))
        templink = os.path.join(TEST_DIR, "temp_link")
        remove(templink)
        assert os.path.isfile(tempf)
        assert os.path.isdir(tempdir)
        assert not os.path.islink(templink)
        remove(tempdir)

    @pytest.mark.skipif(platform.system() == "Windows", reason="Skip on windows")
    def test_remove_symlink_follow(self):
        tempdir = tempfile.mkdtemp(dir=TEST_DIR)
        tempf = tempfile.mkstemp(dir=tempdir)[1]

        os.symlink(tempdir, os.path.join(TEST_DIR, "temp_link"))
        templink = os.path.join(TEST_DIR, "temp_link")
        remove(templink, follow_symlink=True)
        assert not os.path.isfile(tempf)
        assert not os.path.isdir(tempdir)
        assert not os.path.islink(templink)
