from __future__ import annotations

from pathlib import Path
import sys

import pytest

import privacy.filesystem_sandbox as sandbox
from privacy.filesystem_sandbox import (
    FilesystemSandboxError,
    build_filesystem_sandbox_command,
)


def _setenv_values(command: list[str]) -> dict[str, str]:
    values = {}
    for index, value in enumerate(command):
        if value == "--setenv":
            values[command[index + 1]] = command[index + 2]
    return values


def _read_only_mounts(command: list[str]) -> list[tuple[str, str]]:
    mounts = []
    for index, value in enumerate(command):
        if value == "--ro-bind":
            mounts.append(
                (command[index + 1], command[index + 2])
            )
    return mounts


def test_builder_creates_minimal_fail_closed_command(monkeypatch):
    monkeypatch.setattr(
        sandbox.shutil,
        "which",
        lambda name: "/usr/bin/bwrap" if name == "bwrap" else None,
    )

    command = build_filesystem_sandbox_command(
        [
            sys.executable,
            "/app/privacy/encrypted_private_model_worker.py",
        ],
        worker_environment={
            "GVAI_LOCAL_MODEL_NAME": "test-model",
            "GVAI_LOCAL_MODEL_TIMEOUT": "5",
        },
    )

    assert command[0] == "/usr/bin/bwrap"
    for required in (
        "--die-with-parent",
        "--new-session",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-net",
        "--unshare-ipc",
        "--unshare-uts",
        "--clearenv",
    ):
        assert required in command

    environment = _setenv_values(command)
    assert environment == {
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        "PATH": (
            "/usr/local/sbin:/usr/local/bin:"
            "/usr/sbin:/usr/bin:/sbin:/bin"
        ),
        "PYTHONPATH": "/app",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "GVAI_FILESYSTEM_ISOLATED": "1",
        "GVAI_LOCAL_MODEL_NAME": "test-model",
        "GVAI_LOCAL_MODEL_TIMEOUT": "5",
    }

    mounts = _read_only_mounts(command)
    mounted_targets = {target for _, target in mounts}
    assert {
        "/app/privacy/__init__.py",
        "/app/privacy/local_model_worker.py",
        "/app/privacy/workspace_worker_client.py",
        "/app/privacy/encrypted_private_model_worker.py",
    } <= mounted_targets

    separator = command.index("--")
    assert command[separator + 1] == str(
        Path(sys.executable).resolve()
    )
    assert command[separator + 2:] == [
        "/app/privacy/encrypted_private_model_worker.py"
    ]


def test_only_explicit_read_path_is_mounted(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sandbox.shutil,
        "which",
        lambda name: "/usr/bin/bwrap",
    )
    model = tmp_path / "model.gguf"
    model.write_bytes(b"synthetic-model")

    command = build_filesystem_sandbox_command(
        [sys.executable, "-c", "print('ok')"],
        read_only_paths=[model],
    )

    assert (str(model), str(model)) in _read_only_mounts(command)
    assert str(tmp_path) not in {
        target for _, target in _read_only_mounts(command)
    }


@pytest.mark.parametrize("relationship", ["same", "parent", "child"])
def test_protected_boundaries_cannot_be_mounted(
    monkeypatch,
    tmp_path,
    relationship,
):
    monkeypatch.setattr(
        sandbox.shutil,
        "which",
        lambda name: "/usr/bin/bwrap",
    )

    protected = tmp_path / "protected"
    protected.mkdir()
    child = protected / "model.bin"
    child.write_bytes(b"model")

    if relationship == "same":
        allowed = protected
        denied = protected
    elif relationship == "parent":
        allowed = tmp_path
        denied = protected
    else:
        allowed = child
        denied = protected

    with pytest.raises(
        FilesystemSandboxError,
        match="protected boundary",
    ):
        build_filesystem_sandbox_command(
            [sys.executable, "-c", "pass"],
            read_only_paths=[allowed],
            denied_paths=[denied],
        )


@pytest.mark.parametrize(
    ("read_path", "message"),
    [
        ("relative/model.bin", "must be absolute"),
        ("/", "too broad"),
        ("/definitely/not/a/gvai/path", "unavailable"),
    ],
)
def test_invalid_read_paths_fail_closed(
    monkeypatch,
    read_path,
    message,
):
    monkeypatch.setattr(
        sandbox.shutil,
        "which",
        lambda name: "/usr/bin/bwrap",
    )

    with pytest.raises(FilesystemSandboxError, match=message):
        build_filesystem_sandbox_command(
            [sys.executable, "-c", "pass"],
            read_only_paths=[read_path],
        )


def test_missing_bubblewrap_fails_closed(monkeypatch):
    monkeypatch.setattr(
        sandbox.shutil,
        "which",
        lambda name: None,
    )

    with pytest.raises(
        FilesystemSandboxError,
        match="sandbox is unavailable",
    ):
        build_filesystem_sandbox_command(
            [sys.executable, "-c", "pass"]
        )


def test_unapproved_environment_name_fails_closed(monkeypatch):
    monkeypatch.setattr(
        sandbox.shutil,
        "which",
        lambda name: "/usr/bin/bwrap",
    )

    with pytest.raises(
        FilesystemSandboxError,
        match="environment is invalid",
    ):
        build_filesystem_sandbox_command(
            [sys.executable, "-c", "pass"],
            worker_environment={
                "GVAI_PRIVATE_WORKSPACE_KEY": "forbidden"
            },
        )

def test_untrusted_bubblewrap_executable_fails_closed(
    monkeypatch,
    tmp_path,
):
    fake_bubblewrap = tmp_path / "bwrap"
    fake_bubblewrap.write_text(
        "#!/bin/sh\nexit 0\n",
        encoding="utf-8",
    )
    fake_bubblewrap.chmod(0o777)

    monkeypatch.setattr(
        sandbox.shutil,
        "which",
        lambda name: str(fake_bubblewrap),
    )

    with pytest.raises(
        FilesystemSandboxError,
        match="executable is not trusted",
    ):
        build_filesystem_sandbox_command(
            [sys.executable, "-c", "pass"],
        )

def test_sandbox_drops_capabilities_and_blocks_nested_userns():
    command = build_filesystem_sandbox_command(
        [sys.executable, "-c", "pass"],
    )

    assert "--disable-userns" in command
    cap_drop = command.index("--cap-drop")
    assert command[cap_drop + 1] == "ALL"
