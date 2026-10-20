"""Calling shell processes."""

from __future__ import annotations

import shlex
import traceback
from subprocess import PIPE, Popen, TimeoutExpired
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Optional, Self

__author__ = "Matteo Giantomass"
__copyright__ = "Copyright 2014, The Materials Virtual Lab"
__version__ = "0.1"
__maintainer__ = "Matteo Giantomassi"
__email__ = "gmatteo@gmail.com"
__date__ = "10/26/14"


class Command:
    """Run a subprocess command in a separate thread with a timeout.

    The subprocess is terminated if it does not finish within the timeout.

    Attributes:
        retcode: Return code of the subprocess.
        killed: True if the subprocess was killed due to the timeout.
        output: ``stdout`` of the subprocess.
        error: ``stderr`` of the subprocess.

    Examples:
        >>> com = Command("sleep 1").run(timeout=2)
        >>> print(com.retcode, com.killed, com.output, com.output)

    """

    def __init__(self, command: str | Sequence[str]):
        """Initialize the command.

        Args:
            command: Command to execute, either as a shell-like string (split
                with ``shlex``) or as a sequence of arguments.

        """
        self.command: list[str] = (
            shlex.split(command) if isinstance(command, str) else list(command)
        )
        self.process: Popen | None = None
        self.retcode: int | None = None
        self.output, self.error = "", ""
        self.killed = False

    def __str__(self):
        return f"command: {self.command}, retcode: {self.retcode}"

    def run(self, timeout: float | None = None, **kwargs) -> Self:
        """Run the command, waiting up to ``timeout`` seconds.

        Args:
            timeout: Maximum seconds to wait before killing the subprocess.
            **kwargs: Keyword arguments passed to ``Popen``.

        Returns:
            ``self``.

        """

        kwargs.setdefault("stdout", PIPE)
        kwargs.setdefault("stderr", PIPE)

        try:
            with Popen(self.command, **kwargs) as proc:
                self.process = proc
                try:
                    self.output, self.error = proc.communicate(timeout=timeout)
                except TimeoutExpired:
                    proc.terminate()
                    self.output, self.error = proc.communicate()
                    self.killed = True
                self.retcode = proc.returncode
        except Exception:
            self.error = traceback.format_exc()
            self.retcode = -1

        return self
