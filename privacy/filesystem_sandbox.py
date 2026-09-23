"""Fail-closed filesystem and namespace isolation for private workers."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import sys
from typing import Mapping, Sequence


class FilesystemSandboxError(RuntimeError):
    """The private filesystem sandbox could not be constructed."""


_ALLOWED_WORKER_ENV = frozenset(
    {
        "GVAI_LOCAL_MODEL_COMMAND",
        "GVAI_LOCAL_MODEL_NAME",
        "GVAI_LOCAL_MODEL_TIMEOUT",
    }
)

_WORKER_MODULES = (
    "__init__.py",
    "local_model_worker.py",
    "workspace_worker_client.py",
    "encrypted_private_model_worker.py",
)


def _paths_overlap(first: Path, second: Path) -> bool:
    return (
        first == second
        or first in second.parents
        or second in first.parents
    )


def resolve_filesystem_sandbox_executable() -> Path:
    """Return a trusted system-owned Bubblewrap executable."""

    candidate = shutil.which("bwrap")
    if candidate is None:
        raise FilesystemSandboxError(
            "filesystem sandbox is unavailable"
        )

    try:
        resolved = Path(candidate).resolve(strict=True)
        status = resolved.stat()
    except OSError as exc:
        raise FilesystemSandboxError(
            "filesystem sandbox is unavailable"
        ) from exc

    unsafe_permissions = status.st_mode & (
        stat.S_IWGRP | stat.S_IWOTH
    )
    if (
        not stat.S_ISREG(status.st_mode)
        or status.st_uid != 0
        or unsafe_permissions
        or not os.access(resolved, os.X_OK)
    ):
        raise FilesystemSandboxError(
            "filesystem sandbox executable is not trusted"
        )

    return resolved


def _validate_read_paths(
    paths: Sequence[str | os.PathLike[str]],
    denied_paths: Sequence[str | os.PathLike[str]],
) -> tuple[Path, ...]:
    denied = tuple(
        Path(item).resolve(strict=False)
        for item in denied_paths
    )
    validated: list[Path] = []

    for raw_path in paths:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            raise FilesystemSandboxError(
                "sandbox read paths must be absolute"
            )

        try:
            resolved = candidate.resolve(strict=True)
            status = resolved.stat()
        except OSError as exc:
            raise FilesystemSandboxError(
                "sandbox read path is unavailable"
            ) from exc

        if candidate != resolved:
            raise FilesystemSandboxError(
                "sandbox read paths must be canonical"
            )
        if resolved == Path("/"):
            raise FilesystemSandboxError(
                "sandbox read path is too broad"
            )
        if not (
            stat.S_ISREG(status.st_mode)
            or stat.S_ISDIR(status.st_mode)
        ):
            raise FilesystemSandboxError(
                "sandbox read path has unsupported type"
            )
        if any(_paths_overlap(resolved, blocked) for blocked in denied):
            raise FilesystemSandboxError(
                "sandbox read path crosses a protected boundary"
            )
        if resolved not in validated:
            validated.append(resolved)

    return tuple(validated)


def build_filesystem_sandbox_command(
    worker_command: Sequence[str],
    *,
    worker_environment: Mapping[str, str] | None = None,
    read_only_paths: Sequence[str | os.PathLike[str]] = (),
    denied_paths: Sequence[str | os.PathLike[str]] = (),
) -> list[str]:
    """Return a Bubblewrap command for a minimally mounted worker.

    The caller owns all policy inputs. The worker cannot add mounts,
    preserve parent environment variables, or weaken namespace isolation.
    """

    command = [str(part) for part in worker_command]
    if not command:
        raise FilesystemSandboxError(
            "sandbox worker command is empty"
        )

    if sys.platform != "linux":
        raise FilesystemSandboxError(
            "filesystem sandbox requires Linux"
        )

    bubblewrap = resolve_filesystem_sandbox_executable()

    environment = {
        str(name): str(value)
        for name, value in (worker_environment or {}).items()
    }
    if any(name not in _ALLOWED_WORKER_ENV for name in environment):
        raise FilesystemSandboxError(
            "sandbox worker environment is invalid"
        )

    root = Path(__file__).resolve().parents[1]
    privacy_dir = root / "privacy"

    try:
        python_executable = Path(sys.executable).resolve(strict=True)
        python_prefix = Path(sys.base_prefix).resolve(strict=True)
    except OSError as exc:
        raise FilesystemSandboxError(
            "sandbox Python runtime is unavailable"
        ) from exc

    if Path(command[0]).is_absolute():
        try:
            if Path(command[0]).resolve(strict=True) == python_executable:
                command[0] = str(python_executable)
        except OSError:
            pass

    approved_paths = _validate_read_paths(
        read_only_paths,
        denied_paths,
    )

    sandbox = [
        str(bubblewrap),
        "--die-with-parent",
        "--new-session",
        "--unshare-user",
        "--disable-userns",
        "--unshare-pid",
        "--unshare-net",
        "--unshare-ipc",
        "--unshare-uts",
        "--cap-drop",
        "ALL",
        "--clearenv",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/app",
        "--dir",
        "/app/privacy",
        "--ro-bind",
        "/usr",
        "/usr",
        "--symlink",
        "usr/bin",
        "/bin",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--ro-bind",
        str(python_prefix),
        str(python_prefix),
    ]

    for module_name in _WORKER_MODULES:
        source = privacy_dir / module_name
        if not source.is_file():
            raise FilesystemSandboxError(
                "sandbox worker module is unavailable"
            )
        sandbox.extend(
            [
                "--ro-bind",
                str(source),
                f"/app/privacy/{module_name}",
            ]
        )

    for approved_path in approved_paths:
        sandbox.extend(
            [
                "--ro-bind",
                str(approved_path),
                str(approved_path),
            ]
        )

    sandbox.extend(
        [
            "--setenv",
            "HOME",
            "/tmp",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--setenv",
            "PATH",
            "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "--setenv",
            "PYTHONPATH",
            "/app",
            "--setenv",
            "PYTHONDONTWRITEBYTECODE",
            "1",
            "--setenv",
            "PYTHONUNBUFFERED",
            "1",
            "--setenv",
            "GVAI_FILESYSTEM_ISOLATED",
            "1",
        ]
    )

    for name in sorted(environment):
        sandbox.extend(["--setenv", name, environment[name]])

    sandbox.extend(
        [
            "--chdir",
            "/app",
            "--",
            *command,
        ]
    )
    return sandbox
