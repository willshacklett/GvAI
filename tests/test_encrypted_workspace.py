import json
import os
import sys
import time

import pytest

from privacy.encrypted_workspace import (
    AESGCMControlPlane,
    EncryptedProjectWorkspace,
    WorkspaceAuditLog,
    WorkspaceAuthority,
    WorkspaceBroker,
    WorkspaceWorkerError,
)


KEY = bytes(range(32))


def build_broker(
    tmp_path,
    *,
    key=KEY,
    worker_id="worker-1",
    project_id="project-1",
    operations=frozenset({"read", "write"}),
    authorizer=None,
    control_plane=None,
):
    if control_plane is None:
        control_plane = AESGCMControlPlane(
            key,
            authorizer or (lambda request: request.worker_id == "worker-1"),
        )
    adapter = EncryptedProjectWorkspace(
        tmp_path / "storage",
        control_plane,
        WorkspaceAuditLog(tmp_path / "audit.jsonl"),
    )
    return WorkspaceBroker(
        adapter,
        worker_id=worker_id,
        project_id=project_id,
        authority=WorkspaceAuthority(frozenset(operations)),
    )


def run_worker(tmp_path, broker, source, *, timeout=30.0):
    script = tmp_path / f"worker-{len(list(tmp_path.glob('worker-*.py')))}.py"
    script.write_text(source, encoding="utf-8")
    return broker.run_worker([sys.executable, str(script)], timeout=timeout)


def test_authorized_round_trip_is_encrypted_at_rest(tmp_path):
    plaintext = b"private source: launch_code = 7391"
    broker = build_broker(tmp_path)
    run_worker(tmp_path, broker, r'''
import base64
import json
import sys

def request(payload):
    print(json.dumps(payload), flush=True)
    return json.loads(sys.stdin.readline())

plaintext = b"private source: launch_code = 7391"
written = request({"operation": "write", "path": "src/secret.txt", "content_b64": base64.b64encode(plaintext).decode()})
assert written == {"ok": True}
read = request({"operation": "read", "path": "src/secret.txt"})
assert base64.b64decode(read["content_b64"]) == plaintext
''')

    stored = (tmp_path / "storage/project-1/src/secret.txt").read_bytes()
    assert plaintext not in stored
    audit = (tmp_path / "audit.jsonl").read_bytes()
    assert plaintext not in audit
    assert b"worker-1" not in audit
    assert b"project-1" not in audit


def test_worker_client_uses_serialized_pipe_channel(tmp_path):
    broker = build_broker(tmp_path)
    source = """
from privacy.workspace_worker_client import WorkspaceClient

client = WorkspaceClient()
client.write_bytes("client.txt", b"client payload")
assert client.read_bytes("client.txt") == b"client payload"
"""
    assert broker.run_worker([sys.executable, "-c", source]) == 2


def test_wrong_key_and_tampered_ciphertext_are_rejected(tmp_path):
    writer = build_broker(tmp_path)
    run_worker(tmp_path, writer, r'''
import base64, json, sys
print(json.dumps({"operation": "write", "path": "secret.txt", "content_b64": base64.b64encode(b"classified").decode()}), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}
''')

    wrong_key = build_broker(tmp_path, key=b"x" * 32)
    run_worker(tmp_path, wrong_key, r'''
import json, sys
print(json.dumps({"operation": "read", "path": "secret.txt"}), flush=True)
assert json.loads(sys.stdin.readline()) == {"error": "workspace operation failed", "ok": False}
''')

    stored_path = tmp_path / "storage/project-1/secret.txt"
    tampered = bytearray(stored_path.read_bytes())
    tampered[-1] ^= 1
    stored_path.write_bytes(tampered)
    run_worker(tmp_path, writer, r'''
import json, sys
print(json.dumps({"operation": "read", "path": "secret.txt"}), flush=True)
assert json.loads(sys.stdin.readline()) == {"error": "workspace operation failed", "ok": False}
''')
    audit_records = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text().splitlines()
    ]
    assert audit_records[-1]["allowed"] is False
    assert audit_records[-1]["reason"] == "integrity_failure"


def test_malicious_exec_worker_cannot_reach_or_forge_broker_state(tmp_path, monkeypatch):
    monkeypatch.setenv("GVAI_TEST_SECRET", "must-not-enter-worker")
    seen = []
    broker = build_broker(
        tmp_path,
        worker_id="trusted-worker",
        project_id="trusted-project",
        operations=frozenset({"read"}),
        authorizer=lambda request: seen.append(request) or True,
    )
    run_worker(tmp_path, broker, r'''
import gc, json, os, sys
assert "GVAI_TEST_SECRET" not in os.environ
assert "trusted-worker" not in repr(os.environ)
assert "trusted-project" not in repr(os.environ)
for descriptor in range(3, 256):
    try:
        os.fstat(descriptor)
    except OSError:
        continue
    raise AssertionError(f"unexpected inherited fd: {descriptor}")
for item in gc.get_objects():
    assert item.__class__.__name__ not in {"WorkspaceBroker", "EncryptedProjectWorkspace", "AESGCMControlPlane", "WorkspaceAuthority"}

print(json.dumps({"operation": "write", "path": "forged.txt", "content_b64": "bm8=", "worker_id": "worker-1", "project_id": "other", "authority": ["write"]}), flush=True)
assert json.loads(sys.stdin.readline()) == {"error": "workspace request denied", "ok": False}
print(json.dumps({"operation": "write", "path": "forged.txt", "content_b64": "bm8="}), flush=True)
assert json.loads(sys.stdin.readline()) == {"error": "workspace request denied", "ok": False}
''')
    assert seen == []
    assert not (tmp_path / "storage/trusted-project/forged.txt").exists()

    records = [
        json.loads(line)
        for line in (tmp_path / "audit.jsonl").read_text().splitlines()
    ]
    assert [record["reason"] for record in records] == [
        "invalid_request",
        "worker_scope_denied",
    ]


def test_worker_that_closes_protocol_pipe_cannot_hold_broker_open(tmp_path):
    broker = build_broker(tmp_path)
    with pytest.raises(WorkspaceWorkerError, match="workspace worker failed"):
        run_worker(tmp_path, broker, r'''
import os
import time
os.close(1)
time.sleep(10)
    ''', timeout=0.1)


def test_worker_not_reading_large_response_is_killed_and_reaped(tmp_path):
    broker = build_broker(tmp_path)
    run_worker(tmp_path, broker, r'''
import base64
import json
import sys

print(json.dumps({
    "operation": "write",
    "path": "large.bin",
    "content_b64": base64.b64encode(b"x" * (1024 * 1024)).decode(),
}), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}
''')

    process_id_path = tmp_path / "worker.pid"
    source = f'''
import json
import os
import time

with open({str(process_id_path)!r}, "w", encoding="utf-8") as handle:
    handle.write(str(os.getpid()))
    handle.flush()
    os.fsync(handle.fileno())

print(json.dumps({{"operation": "read", "path": "large.bin"}}), flush=True)
time.sleep(10)
'''
    started = time.monotonic()
    with pytest.raises(WorkspaceWorkerError, match="workspace worker failed"):
        run_worker(tmp_path, broker, source, timeout=0.25)
    elapsed = time.monotonic() - started

    assert elapsed < 2.0
    process_id = int(process_id_path.read_text())
    with pytest.raises(ChildProcessError):
        os.waitpid(process_id, os.WNOHANG)
    with pytest.raises(ProcessLookupError):
        os.kill(process_id, 0)


def test_large_response_completes_across_partial_writes(tmp_path):
    broker = build_broker(tmp_path)
    run_worker(tmp_path, broker, r'''
import base64
import json
import sys

content = b"y" * (1024 * 1024)
print(json.dumps({
    "operation": "write",
    "path": "large-readable.bin",
    "content_b64": base64.b64encode(content).decode(),
}), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}

print(json.dumps({
    "operation": "read",
    "path": "large-readable.bin",
}), flush=True)
response = json.loads(sys.stdin.readline())
assert base64.b64decode(response["content_b64"]) == content
''')


class ExplodingControlPlane:
    def __init__(self, operation, delegate=None):
        self.operation = operation
        self.delegate = delegate

    def authorize(self, request):
        if self.operation == "authorize":
            raise RuntimeError("FAKE-PROVIDER-SECRET authorize")
        return True

    def seal(self, plaintext, associated_data):
        if self.operation == "seal":
            raise RuntimeError("FAKE-PROVIDER-SECRET seal")
        return self.delegate.seal(plaintext, associated_data)

    def open(self, ciphertext, associated_data):
        if self.operation == "open":
            raise RuntimeError("FAKE-PROVIDER-SECRET open")
        return self.delegate.open(ciphertext, associated_data)


@pytest.mark.parametrize(
    ("provider_operation", "worker_operation", "reason"),
    [
        ("authorize", "write", "control_plane_error"),
        ("seal", "write", "seal_failure"),
        ("open", "read", "open_failure"),
    ],
)
def test_provider_exceptions_are_sanitized(
    tmp_path,
    provider_operation,
    worker_operation,
    reason,
):
    delegate = AESGCMControlPlane(KEY, lambda request: True)
    if worker_operation == "read":
        writer = build_broker(tmp_path, control_plane=delegate)
        run_worker(tmp_path, writer, r'''
import json, sys
print(json.dumps({"operation": "write", "path": "secret.txt", "content_b64": "c2FmZQ=="}), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}
''')

    broker = build_broker(
        tmp_path,
        control_plane=ExplodingControlPlane(provider_operation, delegate),
    )
    if worker_operation == "write":
        worker_source = r'''
import json, sys
print(json.dumps({"operation": "write", "path": "secret.txt", "content_b64": "c2FmZQ=="}), flush=True)
response = json.loads(sys.stdin.readline())
assert response in [
    {"error": "workspace request denied", "ok": False},
    {"error": "workspace operation failed", "ok": False},
]
assert "FAKE-PROVIDER-SECRET" not in json.dumps(response)
'''
    else:
        worker_source = r'''
import json, sys
print(json.dumps({"operation": "read", "path": "secret.txt"}), flush=True)
response = json.loads(sys.stdin.readline())
assert response == {"error": "workspace operation failed", "ok": False}
assert "FAKE-PROVIDER-SECRET" not in json.dumps(response)
'''
    run_worker(tmp_path, broker, worker_source)

    audit_text = (tmp_path / "audit.jsonl").read_text()
    assert "FAKE-PROVIDER-SECRET" not in audit_text
    assert json.loads(audit_text.splitlines()[-1])["reason"] == reason


@pytest.mark.parametrize(
    ("source_project", "source_path", "target_project", "target_path"),
    [
        ("project-1", "source.txt", "project-1", "other.txt"),
        ("project-1", "source.txt", "project-2", "source.txt"),
    ],
)
def test_ciphertext_cannot_move_between_paths_or_projects(
    tmp_path,
    source_project,
    source_path,
    target_project,
    target_path,
):
    writer = build_broker(tmp_path, project_id=source_project)
    run_worker(tmp_path, writer, f'''
import json, sys
print(json.dumps({{"operation": "write", "path": {source_path!r}, "content_b64": "c2VjcmV0"}}), flush=True)
assert json.loads(sys.stdin.readline()) == {{"ok": True}}
''')
    source = tmp_path / "storage" / source_project / source_path
    target = tmp_path / "storage" / target_project / target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())

    reader = build_broker(tmp_path, project_id=target_project)
    run_worker(tmp_path, reader, f'''
import json, sys
print(json.dumps({{"operation": "read", "path": {target_path!r}}}), flush=True)
assert json.loads(sys.stdin.readline()) == {{"error": "workspace operation failed", "ok": False}}
''')


@pytest.mark.parametrize("path", ["../escape.txt", "/tmp/escape.txt"])
def test_path_traversal_is_rejected_and_audited_without_path(tmp_path, path):
    broker = build_broker(tmp_path)
    run_worker(tmp_path, broker, f'''
import base64, json, sys
print(json.dumps({{"operation": "write", "path": {path!r}, "content_b64": base64.b64encode(b"SENSITIVE-CONTENT").decode()}}), flush=True)
assert json.loads(sys.stdin.readline()) == {{"error": "workspace request denied", "ok": False}}
''')

    record = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[-1])
    assert record["allowed"] is False
    assert record["reason"] == "invalid_path"
    assert "path" not in record
    assert "SENSITIVE" not in json.dumps(record)
    assert "key" not in json.dumps(record).lower()


def test_symlink_escape_is_rejected(tmp_path):
    broker = build_broker(tmp_path)
    project = tmp_path / "storage/project-1"
    project.mkdir(parents=True)
    (project / "outside").symlink_to(tmp_path)
    run_worker(tmp_path, broker, r'''
import json, sys
print(json.dumps({"operation": "write", "path": "outside/escape.txt", "content_b64": "bm8="}), flush=True)
assert json.loads(sys.stdin.readline()) == {"error": "workspace request denied", "ok": False}
''')
    assert not (tmp_path / "escape.txt").exists()


def test_denied_operation_audit_is_sanitized(tmp_path):
    broker = build_broker(
        tmp_path,
        worker_id="intruder",
        project_id="project-1",
        operations=frozenset({"read"}),
        authorizer=lambda request: False,
    )
    run_worker(tmp_path, broker, r'''
import json, sys
print(json.dumps({"operation": "read", "path": "highly-secret-name.txt"}), flush=True)
assert json.loads(sys.stdin.readline()) == {"error": "workspace request denied", "ok": False}
''')

    record_text = (tmp_path / "audit.jsonl").read_text()
    record = json.loads(record_text)
    assert record == pytest.approx(
        {
            "timestamp": record["timestamp"],
            "worker_ref": record["worker_ref"],
            "project_ref": record["project_ref"],
            "operation": "read",
            "allowed": False,
            "reason": "control_plane_denied",
        }
    )
    assert "highly-secret-name" not in record_text
    assert "intruder" not in record_text
    assert "project-1" not in record_text
    assert base64_key_fragment() not in record_text


def base64_key_fragment():
    return "AAECAwQFBgcICQ"