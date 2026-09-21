from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest

import privacy.runtime as runtime
from privacy.encrypted_workspace import WorkspaceBroker


VALID_KEY_B64 = base64.b64encode(bytes(range(32))).decode("ascii")


def _fake_engine(tmp_path: Path) -> Path:
    engine = tmp_path / "fake_engine.py"
    engine.write_text(
        r'''
import sys

prompt = sys.stdin.read()
assert "System:" in prompt
assert "You are GVAI." in prompt
assert "User:" in prompt
assert "top-secret-project-plan" in prompt
assert "Assistant:" in prompt

print("ENCRYPTED-REPLY:top-secret-project-plan")
''',
        encoding="utf-8",
    )
    return engine


def _base_env(monkeypatch, tmp_path, *, fake_engine=True):
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_PRIVATE_ENCRYPTED_WORKSPACE", "1")
    monkeypatch.setenv("GVAI_PRIVATE_WORKSPACE_KEY", VALID_KEY_B64)
    monkeypatch.setenv(
        "GVAI_PRIVATE_WORKSPACE_AUDIT_DIR",
        str(tmp_path / "audit"),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-enter-worker")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-enter-worker")
    if fake_engine:
        engine = _fake_engine(tmp_path)
        monkeypatch.setenv(
            "GVAI_LOCAL_MODEL_COMMAND",
            f"{sys.executable} {engine}",
        )
        monkeypatch.setenv("GVAI_LOCAL_MODEL_NAME", "gvai-encrypted-test")


def _redirect_storage(monkeypatch, tmp_path) -> Path:
    """Make the per-request encrypted storage directory inspectable and
    prevent its cleanup so the test can assert on stored bytes."""

    storage = tmp_path / "workspace-storage"
    storage.mkdir()

    monkeypatch.setattr(
        runtime.tempfile,
        "mkdtemp",
        lambda *args, **kwargs: str(storage),
    )
    monkeypatch.setattr(
        runtime.shutil,
        "rmtree",
        lambda *args, **kwargs: None,
    )
    return storage


def test_encrypted_round_trip_through_exec_worker(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)

    result = runtime.run_private_model_encrypted_workspace(
        "You are GVAI.",
        "top-secret-project-plan",
    )

    assert result == {
        "provider": "local",
        "model": "gvai-encrypted-test",
        "reply": "ENCRYPTED-REPLY:top-secret-project-plan",
        "network_isolated": True,
    }


def test_stored_bytes_never_contain_plaintext(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)
    storage = _redirect_storage(monkeypatch, tmp_path)

    result = runtime.run_private_model_encrypted_workspace(
        "You are GVAI.",
        "top-secret-project-plan",
    )
    assert result["reply"] == "ENCRYPTED-REPLY:top-secret-project-plan"

    stored_files = list(storage.rglob("*"))
    stored_files = [p for p in stored_files if p.is_file()]
    assert stored_files

    for path in stored_files:
        data = path.read_bytes()
        assert b"You are GVAI." not in data
        assert b"top-secret-project-plan" not in data
        assert b"ENCRYPTED-REPLY" not in data
        assert bytes(range(32)) not in data


def test_worker_environment_lacks_key_and_external_credentials(
    monkeypatch, tmp_path
):
    _base_env(monkeypatch, tmp_path, fake_engine=False)

    checker = tmp_path / "checker.py"
    checker.write_text(
        r'''
import sys
prompt = sys.stdin.read()
assert prompt
print("engine-ran")
''',
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        f"{sys.executable} {checker}",
    )

    worker_script = tmp_path / "env_check_worker.py"
    root = Path(__file__).resolve().parents[2]
    worker_script.write_text(
        f'''
import json
import os
import sys
sys.path.insert(0, {str(root)!r})

from privacy.local_model_worker import call_local_model
from privacy.workspace_worker_client import WorkspaceClient

assert "GVAI_PRIVATE_WORKSPACE_KEY" not in os.environ
assert "OPENAI_API_KEY" not in os.environ
assert "ANTHROPIC_API_KEY" not in os.environ

client = WorkspaceClient()
raw = client.read_bytes("request.json")
request = json.loads(raw.decode("utf-8"))
response = call_local_model(request["system_prompt"], request["user_content"])
client.write_bytes("result.json", json.dumps(response).encode("utf-8"))
''',
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND",
        f"{sys.executable} {worker_script}",
    )

    result = runtime.run_private_model_encrypted_workspace(
        "sys prompt",
        "user content",
    )
    assert result["reply"] == "engine-ran"


def test_worker_cannot_reach_control_plane_objects(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)

    worker_script = tmp_path / "probe_worker.py"
    worker_script.write_text(
        r'''
import gc
import json
import sys

for item in gc.get_objects():
    assert item.__class__.__name__ not in {
        "WorkspaceBroker",
        "EncryptedProjectWorkspace",
        "AESGCMControlPlane",
        "WorkspaceAuthority",
    }

print(json.dumps({"operation": "read", "path": "request.json"}), flush=True)
response = json.loads(sys.stdin.readline())
assert response.get("ok") is True

import base64
request = json.loads(base64.b64decode(response["content_b64"]).decode())

print(json.dumps({
    "operation": "write",
    "path": "result.json",
    "content_b64": base64.b64encode(json.dumps({
        "model": "probe",
        "reply": "probe-ok:" + request["user_content"],
    }).encode()).decode(),
}), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}
''',
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND",
        f"{sys.executable} {worker_script}",
    )

    result = runtime.run_private_model_encrypted_workspace(
        "sys",
        "probe-content",
    )
    assert result["reply"] == "probe-ok:probe-content"


def test_worker_cannot_forge_identity_or_authority(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)

    worker_script = tmp_path / "forge_worker.py"
    worker_script.write_text(
        r'''
import base64
import json
import sys

print(json.dumps({
    "operation": "write",
    "path": "forged.txt",
    "content_b64": "bm8=",
    "worker_id": "forged-worker",
    "project_id": "forged-project",
    "authority": ["read", "write", "delete"],
}), flush=True)
denied = json.loads(sys.stdin.readline())
assert denied == {"ok": False, "error": "workspace request denied"}

print(json.dumps({"operation": "read", "path": "request.json"}), flush=True)
response = json.loads(sys.stdin.readline())
assert response["ok"] is True
request = json.loads(base64.b64decode(response["content_b64"]).decode())

print(json.dumps({
    "operation": "write",
    "path": "result.json",
    "content_b64": base64.b64encode(json.dumps({
        "model": "forge-test",
        "reply": "still-authorized:" + request["user_content"],
    }).encode()).decode(),
}), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}
''',
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND",
        f"{sys.executable} {worker_script}",
    )

    result = runtime.run_private_model_encrypted_workspace(
        "sys",
        "forge-content",
    )
    assert result["reply"] == "still-authorized:forge-content"


def test_direct_external_network_access_denied(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path, fake_engine=False)

    engine = tmp_path / "net_engine.py"
    engine.write_text(
        r'''
import socket
import sys

sys.stdin.read()

try:
    socket.create_connection(("1.1.1.1", 443), timeout=1)
except OSError:
    pass
else:
    raise AssertionError("worker escaped network sandbox")

print("no-network-ok")
''',
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        f"{sys.executable} {engine}",
    )

    result = runtime.run_private_model_encrypted_workspace(
        "sys",
        "content",
    )
    assert result["reply"] == "no-network-ok"


@pytest.mark.parametrize(
    "key_value",
    [None, "not-base64!!!", base64.b64encode(b"short").decode("ascii")],
)
def test_missing_malformed_and_wrong_length_keys_fail_closed(
    monkeypatch, tmp_path, key_value
):
    _base_env(monkeypatch, tmp_path)
    if key_value is None:
        monkeypatch.delenv("GVAI_PRIVATE_WORKSPACE_KEY", raising=False)
    else:
        monkeypatch.setenv("GVAI_PRIVATE_WORKSPACE_KEY", key_value)

    def _forbidden_run_worker(self, *args, **kwargs):
        raise AssertionError(
            "worker must not be started when the key is invalid"
        )

    monkeypatch.setattr(WorkspaceBroker, "run_worker", _forbidden_run_worker)

    with pytest.raises(RuntimeError, match="encrypted workspace key"):
        runtime.run_private_model_encrypted_workspace("sys", "content")


def test_worker_failure_does_not_expose_plaintext_keys_or_exceptions(
    monkeypatch, tmp_path
):
    _base_env(monkeypatch, tmp_path, fake_engine=False)

    engine = tmp_path / "failing_engine.py"
    engine.write_text(
        r'''
import sys
sys.stdin.read()
print("SECRET-KEY-LEAK-CANARY " + str(__file__), file=sys.stderr)
raise SystemExit(1)
''',
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        f"{sys.executable} {engine}",
    )

    with pytest.raises(RuntimeError) as excinfo:
        runtime.run_private_model_encrypted_workspace(
            "sys prompt with secrets",
            "user content with secrets",
        )

    message = str(excinfo.value)
    assert message == "GVAI private model worker failed."
    assert "SECRET-KEY-LEAK-CANARY" not in message
    assert VALID_KEY_B64 not in message
    assert str(engine) not in message
    assert "sys prompt with secrets" not in message


def test_feature_flag_disabled_preserves_existing_private_build_behavior(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.delenv("GVAI_PRIVATE_ENCRYPTED_WORKSPACE", raising=False)

    engine = tmp_path / "plain_engine.py"
    engine.write_text(
        'import sys; sys.stdin.read(); print("plain reply")\n',
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "GVAI_PRIVATE_MODEL_COMMAND",
        f"{sys.executable} privacy/local_model_worker.py",
    )
    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        f"{sys.executable} {engine}",
    )

    def _forbidden(*args, **kwargs):
        raise AssertionError("encrypted path must not run when flag is off")

    monkeypatch.setattr(
        runtime, "run_private_model_encrypted_workspace", _forbidden
    )

    result = runtime.run_private_model("sys", "plain content")
    assert result["reply"] == "plain reply"


def test_no_external_model_fallback_when_encrypted_config_invalid(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_PRIVATE_ENCRYPTED_WORKSPACE", "1")
    monkeypatch.delenv("GVAI_PRIVATE_WORKSPACE_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("GVAI_PROVIDER", "openai")

    import gvai.model_router as mod

    with pytest.raises(RuntimeError, match="encrypted workspace key"):
        mod.call_model("system", "content")


def test_audit_entries_contain_only_sanitized_references(monkeypatch, tmp_path):
    _base_env(monkeypatch, tmp_path)

    result = runtime.run_private_model_encrypted_workspace(
        "You are GVAI.",
        "top-secret-project-plan",
    )
    assert result["reply"] == "ENCRYPTED-REPLY:top-secret-project-plan"

    audit_file = tmp_path / "audit" / "audit.jsonl"
    text = audit_file.read_text(encoding="utf-8")

    assert "top-secret-project-plan" not in text
    assert "You are GVAI." not in text
    assert "ENCRYPTED-REPLY" not in text
    assert VALID_KEY_B64 not in text

    for line in text.splitlines():
        record = json.loads(line)
        assert set(record) == {
            "timestamp",
            "worker_ref",
            "project_ref",
            "operation",
            "allowed",
            "reason",
        }
