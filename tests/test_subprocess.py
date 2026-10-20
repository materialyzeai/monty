from __future__ import annotations

import pytest

from monty.subprocess import Command


def test_command():
    """Test Command class"""
    sleep05 = Command("sleep 0.5")

    # NOTE: use a generous timeout relative to the 0.5s sleep. A tight
    # timeout (e.g. 1s) is flaky on Windows CI, where process spawn
    # overhead can push total runtime past the timeout, causing the
    # subprocess to be killed and retcode to be non-zero (PR702).
    sleep05.run(timeout=20)
    full_msg = f"{sleep05=}\n{sleep05.error=}\n{sleep05.output}"
    assert sleep05.retcode == 0, full_msg
    assert not sleep05.killed

    sleep05.run(timeout=0.1)
    assert sleep05.retcode != 0
    assert sleep05.killed


@pytest.mark.parametrize("command", [["sleep", "0.1"], ("sleep", "0.1")])
def test_command_sequence(command):
    com = Command(command)
    assert com.command == ["sleep", "0.1"]
    com.run(timeout=20)
    assert com.retcode == 0
    assert not com.killed


def test_command_timeout_does_not_block():
    import time

    start = time.perf_counter()
    com = Command("sleep 10").run(timeout=0.2)
    assert com.killed
    assert com.retcode != 0
    assert time.perf_counter() - start < 5


def test_command_output():
    com = Command(["python", "-c", "print('hello')"]).run(timeout=20)
    assert com.retcode == 0
    assert com.output.strip() == b"hello"


def test_command_not_found():
    com = Command("monty_nonexistent_executable").run(timeout=20)
    assert com.retcode == -1
    assert "Error" in com.error
