import json
import os
from pathlib import Path
import stat
import sys
import time

import pytest

from privacy.resource_containment import (
    CGROUP_ROOT_ENV,
    CPU_PERIOD_ENV,
    CPU_QUOTA_ENV,
    MEMORY_MAX_ENV,
    PIDS_MAX_ENV,
    CgroupV2Boundary,
    load_worker_resource_configuration,
)

from privacy.encrypted_workspace import (
    AESGCMControlPlane,
    EncryptedProjectWorkspace,
    WorkspaceAuditError,
    WorkspaceAuditLog,
    WorkspaceAuthority,
    WorkspaceBroker,
    WorkspaceRequest,
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


def test_timed_out_worker_and_its_descendant_are_both_terminated(tmp_path):
    """A worker that spawns a long-lived descendant must not leave that
    descendant alive after the broker kills the worker for a protocol
    timeout: both must die, and the direct child must be reaped."""

    broker = build_broker(tmp_path)

    leader_pid_path = tmp_path / "leader.pid"
    descendant_pid_path = tmp_path / "descendant.pid"

    source = f'''
import os
import subprocess
import time

descendant = subprocess.Popen(["sleep", "30"])

with open({str(leader_pid_path)!r}, "w", encoding="utf-8") as handle:
    handle.write(str(os.getpid()))
    handle.flush()
    os.fsync(handle.fileno())

with open({str(descendant_pid_path)!r}, "w", encoding="utf-8") as handle:
    handle.write(str(descendant.pid))
    handle.flush()
    os.fsync(handle.fileno())

# Never speaks the WorkspaceBroker protocol -- forces a timeout.
time.sleep(30)
'''

    started = time.monotonic()
    with pytest.raises(WorkspaceWorkerError, match="workspace worker failed"):
        run_worker(tmp_path, broker, source, timeout=1.0)
    elapsed = time.monotonic() - started
    assert elapsed < 4.0

    deadline = time.monotonic() + 2.0
    while (
        not leader_pid_path.exists() or not descendant_pid_path.exists()
    ) and time.monotonic() < deadline:
        time.sleep(0.05)

    leader_pid = int(leader_pid_path.read_text().strip())
    descendant_pid = int(descendant_pid_path.read_text().strip())

    # The broker's direct child is reaped -- no zombie left behind.
    with pytest.raises(ChildProcessError):
        os.waitpid(leader_pid, os.WNOHANG)
    with pytest.raises(ProcessLookupError):
        os.kill(leader_pid, 0)

    deadline = time.monotonic() + 2.0
    descendant_gone = False
    while time.monotonic() < deadline:
        try:
            os.kill(descendant_pid, 0)
        except ProcessLookupError:
            descendant_gone = True
            break
        time.sleep(0.05)
    assert descendant_gone


def test_failed_worker_group_is_signaled_before_leader_is_reaped(tmp_path, monkeypatch):
    broker = build_broker(tmp_path)
    observed = []
    real_killpg = os.killpg

    def checked_killpg(pgid, sig):
        status = os.waitid(os.P_PID, pgid, os.WEXITED | os.WNOWAIT)
        observed.append((status.si_code, status.si_status))
        return real_killpg(pgid, sig)

    monkeypatch.setattr(os, "killpg", checked_killpg)
    with pytest.raises(WorkspaceWorkerError, match="workspace worker failed"):
        run_worker(tmp_path, broker, "import os; os._exit(7)")

    assert observed == [(os.CLD_EXITED, 7)]


def test_successful_worker_run_does_not_kill_anything(tmp_path):
    broker = build_broker(tmp_path)
    killed = []
    real_killpg = os.killpg

    def spy_killpg(pgid, sig):
        killed.append((pgid, sig))
        return real_killpg(pgid, sig)

    import privacy.encrypted_workspace as ews

    original = ews.os.killpg
    ews.os.killpg = spy_killpg
    try:
        run_worker(tmp_path, broker, r'''
import json
import sys
print(json.dumps({"operation": "write", "path": "ok.txt", "content_b64": "b2s="}), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}
''')
    finally:
        ews.os.killpg = original

    assert killed == []


def test_extra_env_cannot_override_broker_owned_variables(tmp_path):
    broker = build_broker(tmp_path)
    with pytest.raises(WorkspaceWorkerError, match="workspace worker failed"):
        broker.run_worker(
            [sys.executable, "-c", "pass"],
            extra_env={"PATH": "/attacker-controlled"},
        )



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


def test_write_parent_swap_cannot_escape_open_directory(
    tmp_path,
    monkeypatch,
):
    broker = build_broker(tmp_path)
    project = tmp_path / "storage" / "project-1"
    safe = project / "safe"
    original = project / "safe-original"
    outside = tmp_path / "outside"
    safe.mkdir(parents=True)
    outside.mkdir()

    real_replace = os.replace
    swapped = False

    def swap_before_replace(source, destination, **kwargs):
        nonlocal swapped
        if (
            destination == "secret.txt"
            and kwargs.get("dst_dir_fd") is not None
            and not swapped
        ):
            swapped = True
            safe.rename(original)
            safe.symlink_to(outside, target_is_directory=True)

        return real_replace(
            source,
            destination,
            **kwargs,
        )

    monkeypatch.setattr(os, "replace", swap_before_replace)

    run_worker(tmp_path, broker, r"""
import json
import sys

print(json.dumps({
    "operation": "write",
    "path": "safe/secret.txt",
    "content_b64": "c2VjcmV0",
}), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}
""")

    assert swapped is True
    assert not (outside / "secret.txt").exists()
    assert (original / "secret.txt").is_file()


def test_read_parent_swap_uses_open_directory(
    tmp_path,
    monkeypatch,
):
    broker = build_broker(tmp_path)

    run_worker(tmp_path, broker, r"""
import json
import sys

print(json.dumps({
    "operation": "write",
    "path": "safe/secret.txt",
    "content_b64": "c2VjcmV0",
}), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}
""")

    project = tmp_path / "storage" / "project-1"
    safe = project / "safe"
    original = project / "safe-original"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"attacker-controlled")

    real_open = os.open
    swapped = False

    def swap_before_leaf_open(
        file,
        flags,
        mode=0o777,
        *,
        dir_fd=None,
    ):
        nonlocal swapped
        if (
            file == "secret.txt"
            and dir_fd is not None
            and not swapped
        ):
            swapped = True
            safe.rename(original)
            safe.symlink_to(outside, target_is_directory=True)

        if dir_fd is None:
            return real_open(file, flags, mode)
        return real_open(
            file,
            flags,
            mode,
            dir_fd=dir_fd,
        )

    monkeypatch.setattr(os, "open", swap_before_leaf_open)

    run_worker(tmp_path, broker, r"""
import base64
import json
import sys

print(json.dumps({
    "operation": "read",
    "path": "safe/secret.txt",
}), flush=True)
response = json.loads(sys.stdin.readline())
assert response["ok"] is True
assert base64.b64decode(response["content_b64"]) == b"secret"
""")

    assert swapped is True
    assert safe.is_symlink()
    assert (outside / "secret.txt").read_bytes() == b"attacker-controlled"


def test_replaced_workspace_root_is_rejected(
    tmp_path,
):
    broker = build_broker(tmp_path)
    storage = tmp_path / "storage"
    original = tmp_path / "storage-original"

    storage.rename(original)
    storage.mkdir()

    run_worker(tmp_path, broker, r"""
import json
import sys

print(json.dumps({
    "operation": "write",
    "path": "escape.txt",
    "content_b64": "c2VjcmV0",
}), flush=True)
assert json.loads(sys.stdin.readline()) == {
    "error": "workspace request denied",
    "ok": False,
}
""")

    assert not (
        storage / "project-1" / "escape.txt"
    ).exists()

    record = json.loads(
        (tmp_path / "audit.jsonl")
        .read_text()
        .splitlines()[-1]
    )
    assert record["allowed"] is False
    assert record["reason"] == "invalid_path"


def test_audit_symlink_destination_is_rejected(tmp_path):
    outside = tmp_path / "outside-audit.jsonl"
    outside.write_text("attacker-controlled\n", encoding="utf-8")

    audit_path = tmp_path / "audit.jsonl"
    audit_path.symlink_to(outside)

    with pytest.raises(WorkspaceAuditError, match="unavailable"):
        WorkspaceAuditLog(audit_path)

    assert outside.read_text(encoding="utf-8") == (
        "attacker-controlled\n"
    )


def test_audit_file_with_public_permissions_is_rejected(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    audit_path.write_text("", encoding="utf-8")
    audit_path.chmod(0o644)

    with pytest.raises(WorkspaceAuditError, match="invalid"):
        WorkspaceAuditLog(audit_path)


def test_audit_hardlink_is_rejected(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    audit_log = WorkspaceAuditLog(audit_path)
    os.link(audit_path, tmp_path / "audit-copy.jsonl")

    with pytest.raises(WorkspaceAuditError, match="invalid"):
        audit_log.ensure_available()


def test_replaced_audit_directory_fails_before_workspace_mutation(
    tmp_path,
):
    audit_dir = tmp_path / "audit"
    audit_log = WorkspaceAuditLog(audit_dir / "audit.jsonl")

    original = tmp_path / "audit-original"
    audit_dir.rename(original)
    audit_dir.mkdir(mode=0o700)

    storage = tmp_path / "storage"
    control_plane = AESGCMControlPlane(
        KEY,
        lambda request: True,
    )

    with pytest.raises(WorkspaceAuditError, match="unavailable"):
        EncryptedProjectWorkspace(
            storage,
            control_plane,
            audit_log,
        )

    assert not storage.exists()
    assert not (audit_dir / "audit.jsonl").exists()


def test_unavailable_injected_audit_sink_fails_closed(tmp_path):
    authorization_calls = []

    class ControlledAuditSink:
        available = True

        def ensure_available(self):
            if not self.available:
                raise OSError("synthetic audit outage")

        def write(self, request, allowed, reason):
            raise AssertionError(
                "audit write must not run after failed preflight"
            )

    sink = ControlledAuditSink()
    control_plane = AESGCMControlPlane(
        KEY,
        lambda request: authorization_calls.append(request) or True,
    )
    storage = tmp_path / "storage"
    adapter = EncryptedProjectWorkspace(
        storage,
        control_plane,
        sink,
    )

    sink.available = False

    with pytest.raises(WorkspaceAuditError, match="unavailable"):
        adapter.execute(
            WorkspaceRequest(
                "worker-1",
                "project-1",
                "write",
                "secret.txt",
            ),
            WorkspaceAuthority(frozenset({"write"})),
            b"secret",
        )

    assert authorization_calls == []
    assert not (storage / "project-1" / "secret.txt").exists()


def test_audit_append_flushes_file_and_directory(
    tmp_path,
    monkeypatch,
):
    audit_log = WorkspaceAuditLog(tmp_path / "audit.jsonl")
    flushed_modes = []
    real_fsync = os.fsync

    def tracking_fsync(descriptor):
        flushed_modes.append(os.fstat(descriptor).st_mode)
        return real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", tracking_fsync)

    audit_log.write(
        WorkspaceRequest(
            "worker-1",
            "project-1",
            "read",
            "secret.txt",
        ),
        True,
        "authorized",
    )

    assert any(stat.S_ISREG(mode) for mode in flushed_modes)
    assert any(stat.S_ISDIR(mode) for mode in flushed_modes)


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



@pytest.mark.skipif(
    os.getenv("GVAI_RUN_RESOURCE_CONTAINMENT_TEST") != "1",
    reason="real cgroup containment test is opt-in",
)
def test_broker_stages_worker_inside_resource_boundary(tmp_path):
    broker = build_broker(tmp_path)
    script = tmp_path / "contained-workspace-worker.py"
    script.write_text(
        r"""
import json
import sys

request = {
    "operation": "write",
    "path": "contained.txt",
    "content_b64": "Y29udGFpbmVk",
}
print(json.dumps(request), flush=True)
assert json.loads(sys.stdin.readline()) == {"ok": True}
""",
        encoding="utf-8",
    )

    root = Path(
        os.getenv(CGROUP_ROOT_ENV, "/sys/fs/cgroup")
    ).resolve(strict=True)

    configuration = load_worker_resource_configuration(
        {
            CGROUP_ROOT_ENV: str(root),
            MEMORY_MAX_ENV: str(128 * 1024 * 1024),
            PIDS_MAX_ENV: "8",
            CPU_QUOTA_ENV: "20000",
            CPU_PERIOD_ENV: "100000",
        }
    )

    boundary = CgroupV2Boundary(configuration)
    group_path = boundary.path

    try:
        request_count = broker.run_worker(
            [
                str(Path(sys.executable).resolve(strict=True)),
                str(script),
            ],
            timeout=10,
            resource_boundary=boundary,
        )

        assert request_count == 1
        assert boundary.current_process_count() == 0
        assert group_path.exists()
    finally:
        boundary.close()

    assert boundary.closed
    assert not group_path.exists()
