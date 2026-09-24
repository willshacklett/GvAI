"""Trusted stop-before-exec launcher for private worker containment.

The launcher creates no descendants. It stops itself before executing the
worker so the trusted broker can attach its PID to an externally controlled
resource boundary. Only after attachment does the broker send SIGCONT.
"""

from __future__ import annotations

import os
from pathlib import Path
import signal
import sys
from typing import Sequence


USAGE_ERROR = 64
EXEC_ERROR = 126


def main(argv: Sequence[str] | None = None) -> int:
    command = list(sys.argv[1:] if argv is None else argv)
    if not command:
        return USAGE_ERROR

    executable = Path(command[0])
    if not executable.is_absolute():
        return USAGE_ERROR

    try:
        resolved = executable.resolve(strict=True)
    except OSError:
        return EXEC_ERROR

    if resolved != executable or not resolved.is_file():
        return EXEC_ERROR

    # No worker code or descendant exists before this stop. The trusted
    # broker must attach this PID to the resource boundary before SIGCONT.
    os.kill(os.getpid(), signal.SIGSTOP)

    try:
        os.execve(str(resolved), command, os.environ)
    except OSError:
        return EXEC_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
