"""Opt-in Linux smoke test: real sandbox, synthetic data, no model service."""

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import sys

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from privacy.model_asset_provenance import MANIFEST_SCHEMA


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
    cgroup_root = Path(
        os.environ.get(
            "GVAI_PRIVATE_CGROUP_ROOT",
            "/sys/fs/cgroup",
        )
    ).resolve(strict=True)
    cgroups_before = {
        entry.name
        for entry in cgroup_root.glob("gvai-worker-*")
    }
    model_asset = tmp_path / "synthetic-model.asset"
    asset_content = (
        "synthetic-approved-model-asset-"
        + secrets.token_hex(16)
    ).encode("ascii")
    model_asset.write_bytes(asset_content)
    canonical_asset = str(model_asset.resolve(strict=True))

    entries = [
        {
            "path": canonical_asset,
            "sha256": hashlib.sha256(asset_content).hexdigest(),
            "size": len(asset_content),
        }
    ]
    signed_payload = json.dumps(
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
                    private_key.sign(signed_payload)
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
    public_key_b64 = base64.b64encode(public_key).decode("ascii")

    forbidden = sorted(
        runtime.EXTERNAL_SECRET_ENV
        | runtime.RESOURCE_POLICY_ENV_NAMES
        | {
            runtime.ENCRYPTED_WORKSPACE_KEY_ENV,
            runtime.ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV,
            runtime.FILESYSTEM_SANDBOX_READ_PATHS_ENV,
            runtime.MODEL_ASSET_MANIFEST_ENV,
            runtime.MODEL_ASSET_PUBLIC_KEY_ENV,
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
assert not Path({str(manifest)!r}).exists()

model_asset = Path({canonical_asset!r})
assert model_asset.read_bytes() == {asset_content!r}
try:
    model_asset.write_bytes(b"worker-mutation-must-fail")
except OSError:
    pass
else:
    raise AssertionError("approved model asset was writable")

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
        runtime.FILESYSTEM_SANDBOX_READ_PATHS_ENV,
        canonical_asset,
    )
    monkeypatch.setenv(
        runtime.MODEL_ASSET_MANIFEST_ENV,
        str(manifest.resolve(strict=True)),
    )
    monkeypatch.setenv(
        runtime.MODEL_ASSET_PUBLIC_KEY_ENV,
        public_key_b64,
    )
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
    cgroups_after = {
        entry.name
        for entry in cgroup_root.glob("gvai-worker-*")
    }
    assert cgroups_after == cgroups_before

    audit_file = audit_dir / "audit.jsonl"
    assert audit_dir.stat().st_mode & 0o777 == 0o700
    assert audit_file.stat().st_mode & 0o777 == 0o600
    audit = audit_file.read_text(encoding="utf-8")
    records = [json.loads(line) for line in audit.splitlines()]
    assert records
    for forbidden_value in (
        marker,
        reply,
        key,
        public_key_b64,
        asset_content.decode("ascii"),
        "synthetic-not-a-credential",
    ):
        assert forbidden_value not in audit
