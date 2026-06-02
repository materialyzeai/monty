from __future__ import annotations

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
