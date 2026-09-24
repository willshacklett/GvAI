from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from privacy import resource_staging_launcher as launcher


def test_launcher_rejects_empty_or_relative_command():
    assert launcher.main([]) == launcher.USAGE_ERROR
    assert launcher.main(["python", "-c", "pass"]) == launcher.USAGE_ERROR


def test_launcher_rejects_missing_absolute_command(tmp_path):
    missing = tmp_path / "missing-worker"
    assert launcher.main([str(missing)]) == launcher.EXEC_ERROR


def test_launcher_stops_before_worker_executes(tmp_path):
    python = Path(sys.executable).resolve(strict=True)
    launcher_path = Path(launcher.__file__).resolve(strict=True)
    marker = tmp_path / "worker-executed"

    worker_code = (
        "from pathlib import Path;"
        f"Path({str(marker)!r}).write_text("
        "'executed', encoding='utf-8')"
    )

    process = subprocess.Popen(
        [
            str(python),
            str(launcher_path),
            str(python),
            "-c",
            worker_code,
        ],
        env={
            "PATH": os.defpath,
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        start_new_session=True,
    )

    try:
        deadline = time.monotonic() + 5.0
        stopped = False

        while time.monotonic() < deadline:
            waited_pid, status = os.waitpid(
                process.pid,
                os.WNOHANG | os.WUNTRACED,
            )
            if waited_pid == process.pid and os.WIFSTOPPED(status):
                stopped = True
                break
            if process.poll() is not None:
                break
            time.sleep(0.02)

        assert stopped
        assert process.poll() is None
        assert not marker.exists()

        os.kill(process.pid, signal.SIGCONT)

        assert process.wait(timeout=5) == 0
        assert marker.read_text(encoding="utf-8") == "executed"
    finally:
        if process.poll() is None:
            os.kill(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
