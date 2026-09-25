import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from privacy import filesystem_sandbox
from privacy import resource_containment
from privacy import runtime
from privacy import staging_readiness as readiness
from privacy.model_asset_provenance import MANIFEST_SCHEMA


@pytest.fixture
def configured(monkeypatch, tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.touch(mode=0o700)
    worker = tmp_path / "worker.py"
    worker.touch()
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir(mode=0o700)

    monkeypatch.setattr(runtime, "SANDBOX", sandbox)
    monkeypatch.setattr(runtime, "ENCRYPTED_WORKER_SCRIPT", worker)
    monkeypatch.setattr(readiness.sys, "platform", "linux")
    monkeypatch.setattr(
        filesystem_sandbox.shutil,
        "which",
        lambda name: "/usr/bin/bwrap" if name == "bwrap" else None,
    )

    class FakeResourceBoundary:
        def __init__(self, configuration):
            self.configuration = configuration
            self.closed = False

        def close(self):
            self.closed = True

    monkeypatch.setattr(
        resource_containment,
        "CgroupV2Boundary",
        FakeResourceBoundary,
    )
    monkeypatch.setenv(
        resource_containment.CGROUP_ROOT_ENV,
        str(cgroup_root),
    )

    for name in (
        "posix_spawnp", "POSIX_SPAWN_CLOSEFROM", "pidfd_open",
        "killpg", "waitid", "P_PID", "WEXITED", "WNOWAIT", "CLD_EXITED",
        "WSTOPPED", "WNOHANG", "CLD_STOPPED",
    ):
        if not hasattr(os, name):
            monkeypatch.setattr(os, name, object(), raising=False)

    real_readlink = os.readlink

    def synthetic_readlink(path):
        if str(path).startswith("/proc/self/ns/"):
            return "namespace:[synthetic-parent]"
        return real_readlink(path)

    monkeypatch.setattr(os, "readlink", synthetic_readlink)
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_PRIVATE_ENCRYPTED_WORKSPACE", "1")
    monkeypatch.delenv(
        runtime.ENCRYPTED_WORKSPACE_KEY_ENV,
        raising=False,
    )
    monkeypatch.setenv(
        runtime.WORKSPACE_KEY_SOCKET_ENV,
        "/synthetic/trusted-key-provider.sock",
    )
    monkeypatch.setenv(
        runtime.WORKSPACE_KEY_PROVIDER_UID_ENV,
        str(os.geteuid()),
    )
    monkeypatch.setattr(
        runtime,
        "load_workspace_key_from_provider",
        lambda: bytes(range(32)),
    )
    monkeypatch.setenv("GVAI_LOCAL_MODEL_COMMAND", "synthetic-engine")
    monkeypatch.setenv(
        runtime.ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV,
        str(tmp_path / "audit"),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    monkeypatch.delenv(
        "GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND",
        raising=False,
    )

    model_asset = tmp_path / "synthetic-model.asset"
    model_content = b"synthetic-approved-model-asset"
    model_asset.write_bytes(model_content)
    canonical_asset = str(model_asset.resolve(strict=True))
    monkeypatch.setenv(
        runtime.FILESYSTEM_SANDBOX_READ_PATHS_ENV,
        canonical_asset,
    )

    entries = [
        {
            "path": canonical_asset,
            "sha256": hashlib.sha256(model_content).hexdigest(),
            "size": len(model_content),
        }
    ]
    payload = json.dumps(
        {
            "assets": entries,
            "schema": MANIFEST_SCHEMA,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    private_key = Ed25519PrivateKey.generate()
    manifest = tmp_path / "signed-model-assets.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "assets": entries,
                "signature": base64.b64encode(
                    private_key.sign(payload)
                ).decode("ascii"),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    monkeypatch.setenv(
        runtime.MODEL_ASSET_MANIFEST_ENV,
        str(manifest.resolve(strict=True)),
    )
    monkeypatch.setenv(
        runtime.MODEL_ASSET_PUBLIC_KEY_ENV,
        base64.b64encode(public_key).decode("ascii"),
    )

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(readiness.subprocess, "run", fake_run)
    return calls


def test_configured_preflight_passes_without_claiming_production(configured):
    report = readiness.check_readiness()

    assert report["scope"] == "configuration_and_namespace_preflight"
    assert report["ready_for_smoke_test"] is True
    assert report["production_ready"] is False
    assert report["checks"]["audit_destination"] == "pass"
    assert report["checks"]["key_configuration"] == "pass"
    assert report["checks"]["external_key_provider"] == "pass"
    assert report["checks"]["resource_policy"] == "pass"
    assert report["checks"]["resource_containment"] == "pass"
    assert report["checks"]["model_asset_provenance"] == "pass"
    assert "approved_model_asset_content" not in report["not_verified"]
    assert "concurrent_host_asset_mutation" in report["not_verified"]
    assert "filesystem_isolation" not in report["not_verified"]
    assert "resource_limits" not in report["not_verified"]
    assert (
        "escaped_descendant_containment"
        not in report["not_verified"]
    )
    assert (
        "independently_protected_audit_storage"
        in report["not_verified"]
    )
    assert (
        "cross_resource_audit_atomicity"
        in report["not_verified"]
    )

    audit_dir = Path(
        os.environ[runtime.ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV]
    )
    assert audit_dir.is_dir()
    assert (audit_dir / "audit.jsonl").is_file()

    for name in (
        "network_namespace",
        "mount_namespace",
        "pid_namespace",
        "filesystem_isolation",
    ):
        assert report["checks"][name] == "pass"

    assert len(configured) == 1
    command, kwargs = configured[0]
    assert command[0] == "/usr/bin/bwrap"
    assert "--unshare-net" in command
    assert "--unshare-pid" in command
    assert "--clearenv" in command
    assert "synthetic-engine" not in command
    assert kwargs["env"] == {"PATH": os.defpath, "LANG": "C"}
    assert kwargs["timeout"] == 10
    assert kwargs["close_fds"] is True
    assert "synthetic-secret" not in json.dumps(report)


@pytest.mark.parametrize("name,check", [
    ("GVAI_PRIVATE_BUILD_MODE", "private_mode"),
    ("GVAI_PRIVATE_ENCRYPTED_WORKSPACE", "encrypted_mode"),
    ("GVAI_LOCAL_MODEL_COMMAND", "model_command_syntax"),
])
def test_missing_configuration_fails(configured, monkeypatch, name, check):
    monkeypatch.delenv(name, raising=False)
    report = readiness.check_readiness()
    assert report["checks"][check] == "fail"
    assert report["ready_for_smoke_test"] is False


def test_missing_external_key_provider_fails(
    configured,
    monkeypatch,
):
    monkeypatch.delenv(
        runtime.WORKSPACE_KEY_SOCKET_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        runtime.WORKSPACE_KEY_PROVIDER_UID_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        runtime.ENCRYPTED_WORKSPACE_KEY_ENV,
        raising=False,
    )

    report = readiness.check_readiness()

    assert report["checks"]["key_configuration"] == "fail"
    assert report["checks"]["external_key_provider"] == "fail"
    assert report["ready_for_smoke_test"] is False
    assert configured == []


def test_environment_key_fallback_is_not_staging_ready(
    configured,
    monkeypatch,
):
    monkeypatch.delenv(
        runtime.WORKSPACE_KEY_SOCKET_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        runtime.WORKSPACE_KEY_PROVIDER_UID_ENV,
        raising=False,
    )
    monkeypatch.setenv(
        runtime.ENCRYPTED_WORKSPACE_KEY_ENV,
        base64.b64encode(bytes(range(32))).decode("ascii"),
    )

    report = readiness.check_readiness()

    assert report["checks"]["key_configuration"] == "pass"
    assert report["checks"]["external_key_provider"] == "fail"
    assert report["ready_for_smoke_test"] is False
    assert configured == []


def test_invalid_model_asset_provenance_fails_sanitized(
    configured,
    monkeypatch,
):
    model_asset = Path(
        os.environ[runtime.FILESYSTEM_SANDBOX_READ_PATHS_ENV]
    )
    sensitive_content = "SENSITIVE-MUTATED-MODEL-ASSET"
    model_asset.write_text(sensitive_content, encoding="utf-8")

    report = readiness.check_readiness()

    assert report["checks"]["model_asset_provenance"] == "fail"
    assert report["ready_for_smoke_test"] is False
    serialized = json.dumps(report)
    assert sensitive_content not in serialized
    assert str(model_asset) not in serialized


def test_provider_failure_is_not_reported(configured, monkeypatch):
    sensitive_error = "SENSITIVE-PROVIDER-FAILURE"

    def fail_provider():
        raise RuntimeError(sensitive_error)

    monkeypatch.setattr(
        runtime,
        "load_workspace_key_from_provider",
        fail_provider,
    )

    report = readiness.check_readiness()

    assert report["checks"]["key_configuration"] == "fail"
    assert report["checks"]["external_key_provider"] == "fail"
    assert report["ready_for_smoke_test"] is False
    assert sensitive_error not in json.dumps(report)


def test_insecure_audit_destination_fails_sanitized(
    configured,
    monkeypatch,
):
    audit_dir = Path(
        os.environ[runtime.ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV]
    )
    audit_dir.mkdir(mode=0o700)
    audit_file = audit_dir / "audit.jsonl"
    audit_file.write_text(
        "SENSITIVE-AUDIT-CANARY",
        encoding="utf-8",
    )
    audit_file.chmod(0o644)

    report = readiness.check_readiness()

    assert report["checks"]["audit_destination"] == "fail"
    assert report["ready_for_smoke_test"] is False
    serialized = json.dumps(report)
    assert "SENSITIVE-AUDIT-CANARY" not in serialized
    assert str(audit_file) not in serialized


def test_relative_audit_destination_fails_sanitized(
    configured,
    monkeypatch,
):
    configured_path = "SENSITIVE-RELATIVE-AUDIT-PATH"
    monkeypatch.setenv(
        runtime.ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV,
        configured_path,
    )

    report = readiness.check_readiness()

    assert report["checks"]["audit_destination"] == "fail"
    assert report["ready_for_smoke_test"] is False
    assert configured_path not in json.dumps(report)


def test_sandbox_nonzero_fails(configured, monkeypatch):
    monkeypatch.setattr(
        readiness.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )
    report = readiness.check_readiness()
    assert report["checks"]["network_namespace"] == "fail"
    assert report["checks"]["filesystem_isolation"] == "fail"
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


def test_missing_bubblewrap_blocks_probe(configured, monkeypatch):
    monkeypatch.setattr(
        filesystem_sandbox.shutil,
        "which",
        lambda name: None,
    )
    report = readiness.check_readiness()
    assert report["checks"]["filesystem_sandbox_executable"] == "fail"
    assert report["ready_for_smoke_test"] is False
    assert configured == []


def test_worker_override_requires_review(configured, monkeypatch):
    monkeypatch.setenv(
        "GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND",
        "custom-worker",
    )
    report = readiness.check_readiness()
    assert report["checks"]["stock_worker"] == "fail"
    assert report["ready_for_smoke_test"] is False
    assert configured == []


def test_cli_exit_codes(configured, monkeypatch, capsys):
    assert readiness.main() == 0
    assert json.loads(
        capsys.readouterr().out
    )["ready_for_smoke_test"] is True

    monkeypatch.delenv(runtime.WORKSPACE_KEY_SOCKET_ENV)
    assert readiness.main() == 1
    assert json.loads(
        capsys.readouterr().out
    )["ready_for_smoke_test"] is False

def test_untrusted_bubblewrap_blocks_probe(
    configured,
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
        filesystem_sandbox.shutil,
        "which",
        lambda name: str(fake_bubblewrap),
    )

    report = readiness.check_readiness()

    assert (
        report["checks"]["filesystem_sandbox_executable"]
        == "fail"
    )
    assert report["ready_for_smoke_test"] is False
    assert configured == []



def test_invalid_resource_policy_fails_sanitized(
    configured,
    monkeypatch,
):
    canary = "SENSITIVE-RESOURCE-POLICY-CANARY"
    monkeypatch.setenv(
        resource_containment.PIDS_MAX_ENV,
        canary,
    )

    report = readiness.check_readiness()

    assert report["checks"]["resource_policy"] == "fail"
    assert report["checks"]["resource_containment"] == "fail"
    assert report["ready_for_smoke_test"] is False
    assert canary not in json.dumps(report)
    assert configured == []


def test_unavailable_resource_boundary_fails_sanitized(
    configured,
    monkeypatch,
):
    def unavailable(*args, **kwargs):
        raise PermissionError(
            "SENSITIVE-CGROUP-FAILURE-CANARY"
        )

    monkeypatch.setattr(
        resource_containment,
        "CgroupV2Boundary",
        unavailable,
    )

    report = readiness.check_readiness()

    assert report["checks"]["resource_policy"] == "pass"
    assert report["checks"]["resource_containment"] == "fail"
    assert report["ready_for_smoke_test"] is False
    assert (
        "SENSITIVE-CGROUP-FAILURE-CANARY"
        not in json.dumps(report)
    )
    assert configured == []
