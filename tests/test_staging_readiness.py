import base64
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from privacy import runtime
from privacy import staging_readiness as readiness


@pytest.fixture
def configured(monkeypatch, tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.touch(mode=0o700)
    worker = tmp_path / "worker.py"
    worker.touch()
    monkeypatch.setattr(runtime, "SANDBOX", sandbox)
    monkeypatch.setattr(runtime, "ENCRYPTED_WORKER_SCRIPT", worker)
    monkeypatch.setattr(readiness.sys, "platform", "linux")
    for name in (
        "posix_spawnp", "POSIX_SPAWN_CLOSEFROM", "pidfd_open",
        "killpg", "waitid", "P_PID", "WEXITED", "WNOWAIT", "CLD_EXITED",
    ):
        if not hasattr(os, name):
            monkeypatch.setattr(os, name, object(), raising=False)
    monkeypatch.setattr(os, "readlink", lambda path: "net:[synthetic-parent]")
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_PRIVATE_ENCRYPTED_WORKSPACE", "1")
    monkeypatch.setenv(
        "GVAI_PRIVATE_WORKSPACE_KEY",
        base64.b64encode(bytes(range(32))).decode("ascii"),
    )
    monkeypatch.setenv("GVAI_LOCAL_MODEL_COMMAND", "synthetic-engine")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    monkeypatch.delenv("GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND", raising=False)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(readiness.subprocess, "run", fake_run)
    return calls


def test_configured_preflight_passes_without_claiming_production(configured):
    report = readiness.check_readiness()
    assert report["ready_for_smoke_test"] is True
    assert report["production_ready"] is False
    assert "filesystem_isolation" in report["not_verified"]
    assert len(configured) == 1
    command, kwargs = configured[0]
    assert command[0] == str(runtime.SANDBOX)
    assert "synthetic-engine" not in command
    assert kwargs["env"] == {"PATH": os.defpath, "LANG": "C"}
    assert kwargs["timeout"] == 10
    assert kwargs["close_fds"] is True
    assert "synthetic-secret" not in json.dumps(report)


@pytest.mark.parametrize("name,check", [
    ("GVAI_PRIVATE_BUILD_MODE", "private_mode"),
    ("GVAI_PRIVATE_ENCRYPTED_WORKSPACE", "encrypted_mode"),
    ("GVAI_PRIVATE_WORKSPACE_KEY", "key_configuration"),
    ("GVAI_LOCAL_MODEL_COMMAND", "model_command_syntax"),
])
def test_missing_configuration_fails(configured, monkeypatch, name, check):
    monkeypatch.delenv(name, raising=False)
    report = readiness.check_readiness()
    assert report["checks"][check] == "fail"
    assert report["ready_for_smoke_test"] is False


def test_malformed_key_is_not_reported(configured, monkeypatch):
    monkeypatch.setenv("GVAI_PRIVATE_WORKSPACE_KEY", "secret-invalid-key!")
    report = readiness.check_readiness()
    assert report["checks"]["key_configuration"] == "fail"
    assert "secret-invalid-key!" not in json.dumps(report)


def test_sandbox_nonzero_fails(configured, monkeypatch):
    monkeypatch.setattr(
        readiness.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )
    report = readiness.check_readiness()
    assert report["checks"]["network_namespace"] == "fail"
    assert report["ready_for_smoke_test"] is False


@pytest.mark.parametrize("error", [
    PermissionError("synthetic-sensitive-error"),
    subprocess.TimeoutExpired("synthetic-sensitive-error", 10),
])
def test_sandbox_errors_are_sanitized(configured, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(readiness.subprocess, "run", fail)
    report = readiness.check_readiness()
    assert report["ready_for_smoke_test"] is False
    assert "synthetic-sensitive-error" not in json.dumps(report)


def test_missing_process_api_blocks_probe(configured, monkeypatch):
    monkeypatch.delattr(os, "pidfd_open")
    report = readiness.check_readiness()
    assert report["checks"]["process_api"] == "fail"
    assert report["ready_for_smoke_test"] is False
    assert configured == []


def test_worker_override_requires_review(configured, monkeypatch):
    monkeypatch.setenv("GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND", "custom-worker")
    report = readiness.check_readiness()
    assert report["checks"]["stock_worker"] == "fail"
    assert report["ready_for_smoke_test"] is False


def test_cli_exit_codes(configured, monkeypatch, capsys):
    assert readiness.main() == 0
    assert json.loads(capsys.readouterr().out)["ready_for_smoke_test"] is True
    monkeypatch.delenv("GVAI_PRIVATE_WORKSPACE_KEY")
    assert readiness.main() == 1
    assert json.loads(capsys.readouterr().out)["ready_for_smoke_test"] is False
