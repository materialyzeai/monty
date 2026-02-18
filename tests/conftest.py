from __future__ import annotations

import os
import shutil
import tempfile

import pytest


@pytest.fixture()
def tmp_dir():
    """Run test in isolated test directory."""

    old_cwd = os.getcwd()
    new_path = tempfile.mkdtemp()
    os.chdir(new_path)
    yield
    os.chdir(old_cwd)
    shutil.rmtree(new_path)
