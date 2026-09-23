"""Opt-in Linux smoke test: real sandbox, synthetic data, no model service."""

import base64
import json
import os
from pathlib import Path
import secrets
import shlex
import sys

import pytest


@pytest.mark.skipif(
    os.environ.get("GVAI_RUN_STAGING_SMOKE") != "1",
    reason="Set GVAI_RUN_STAGING_SMOKE=1 to exercise the real sandbox.",
)
def test_real_encrypted_runtime_boundary(monkeypatch, tmp_path):
    import privacy.runtime as runtime

    root = Path(__file__).resolve().parents[2]
    parent_namespaces = {
        name: os.readlink(f"/proc/self/ns/{name}")
        for name in ("mnt", "net", "pid")
    }
    host_home = str(Path.home())
    marker = "synthetic-staging-" + secrets.token_hex(16)
    reply = "synthetic-reply-" + secrets.token_hex(16)
    key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    audit_dir = tmp_path / "audit"
    forbidden = sorted(
        runtime.EXTERNAL_SECRET_ENV
        | {
            runtime.ENCRYPTED_WORKSPACE_KEY_ENV,
            runtime.ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV,
            runtime.FILESYSTEM_SANDBOX_READ_PATHS_ENV,
        }
    )

    # The engine receives plaintext legitimately, but not parent secrets.
    # Namespace/interface checks do not contact any external endpoint.
    engine = f"""
import os
from pathlib import Path
import socket
import sys

for name, parent in {parent_namespaces!r}.items():
    assert os.readlink("/proc/self/ns/" + name) != parent

assert set(name for _, name in socket.if_nameindex()) <= {{"lo"}}
assert all(name not in os.environ for name in {forbidden!r})
assert os.environ["GVAI_FILESYSTEM_ISOLATED"] == "1"
assert os.environ["HOME"] == "/tmp"
assert not Path({str(root)!r}).exists()
assert not Path({host_home!r}).exists()
assert not Path({str(audit_dir)!r}).exists()

private_temp = Path("/tmp/staging-private.txt")
private_temp.write_text("private", encoding="utf-8")
assert private_temp.read_text(encoding="utf-8") == "private"

prompt = sys.stdin.read()
assert {marker!r} in prompt
assert "System:" in prompt and "Assistant:" in prompt
print({reply!r})
"""

    monkeypatch.setattr(runtime, "SANDBOX", root / "privacy/run_network_sandbox.sh")
    monkeypatch.setattr(
        runtime,
        "ENCRYPTED_WORKER_SCRIPT",
        root / "privacy/encrypted_private_model_worker.py",
    )
    monkeypatch.delenv("GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND", raising=False)
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_PRIVATE_ENCRYPTED_WORKSPACE", "1")
    monkeypatch.setenv("GVAI_PRIVATE_WORKSPACE_KEY", key)
    monkeypatch.setenv("GVAI_PRIVATE_WORKSPACE_AUDIT_DIR", str(audit_dir))
    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        shlex.join([sys.executable, "-I", "-c", engine]),
    )
    monkeypatch.setenv("GVAI_LOCAL_MODEL_NAME", "staging-synthetic")
    monkeypatch.setenv("GVAI_LOCAL_MODEL_TIMEOUT", "5")
    for name in runtime.EXTERNAL_SECRET_ENV:
        monkeypatch.setenv(name, "synthetic-not-a-credential")

    # Observe actual allocation; do not disable or replace cleanup.
    allocated = []
    real_mkdtemp = runtime.tempfile.mkdtemp

    def tracked_mkdtemp(*args, **kwargs):
        directory = real_mkdtemp(*args, **kwargs)
        if kwargs.get("prefix") == "gvai-private-ws-":
            allocated.append(Path(directory))
        return directory

    monkeypatch.setattr(runtime.tempfile, "mkdtemp", tracked_mkdtemp)
    result = runtime.run_private_model(
        "Synthetic staging check only.",
        marker,
        timeout=10,
    )
    assert result == {
        "provider": "local",
        "model": "staging-synthetic",
        "reply": reply,
        "network_isolated": True,
    }
    assert allocated
    assert all(not directory.exists() for directory in allocated)

    audit = (audit_dir / "audit.jsonl").read_text(encoding="utf-8")
    records = [json.loads(line) for line in audit.splitlines()]
    assert records
    for forbidden_value in (marker, reply, key, "synthetic-not-a-credential"):
        assert forbidden_value not in audit
