"""
GVAI Private Build Runtime.

Private Build Mode executes model work through isolated worker
processes. The encrypted-workspace path uses Bubblewrap filesystem,
process, and network namespaces. External model credentials are stripped
from the worker environment.

Default (non-encrypted) worker protocol -- one-shot stdin/stdout:

stdin:
{
    "system_prompt": "...",
    "user_content": "..."
}

stdout:
{
    "model": "...",
    "reply": "..."
}

Opt-in encrypted-workspace protocol (GVAI_PRIVATE_ENCRYPTED_WORKSPACE=1):

This process (the trusted parent) owns the encryption control plane, the
AES-GCM key, project/worker identity, and operation authority. It never
hands any of those to the worker. It seals the request into an encrypted
workspace, execs a filesystem- and network-isolated worker through Bubblewrap.
The worker reads and writes exclusively through
privacy.workspace_worker_client.WorkspaceClient
(see privacy/encrypted_workspace.py and privacy/encrypted_private_model_worker.py),
and then opens the sealed result itself. The worker's stdin/stdout are the
WorkspaceBroker's JSON-lines request/response channel -- they are never
reused for the old one-shot protocol above.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Dict, Any, Optional

from privacy.encrypted_workspace import (
    AESGCMControlPlane,
    EncryptedProjectWorkspace,
    WorkspaceAuditLog,
    WorkspaceAuthority,
    WorkspaceBroker,
    WorkspaceRequest,
    WorkspaceWorkerError,
)
from privacy.filesystem_sandbox import (
    FilesystemSandboxError,
    build_filesystem_sandbox_command,
)


ROOT = Path(__file__).resolve().parents[1]

SANDBOX = (
    ROOT
    / "privacy"
    / "run_network_sandbox.sh"
)

ENCRYPTED_WORKER_SCRIPT = (
    ROOT
    / "privacy"
    / "encrypted_private_model_worker.py"
)

EXTERNAL_SECRET_ENV = {
    "OPENAI_API_KEY",
    "OPENAI_COMPAT_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROK_API_KEY",
    "XAI_API_KEY",
}

# Non-secret local-inference configuration the encrypted worker needs to
# invoke the same local engine as the non-encrypted path. Nothing in this
# list may ever hold a credential or the workspace key. This is a fixed
# allowlist, not a denylist: only these exact names can ever reach the
# worker through extra_env.
_LOCAL_MODEL_CONFIG_ENV = (
    "GVAI_LOCAL_MODEL_COMMAND",
    "GVAI_LOCAL_MODEL_NAME",
    "GVAI_LOCAL_MODEL_TIMEOUT",
)

ENCRYPTED_WORKSPACE_KEY_ENV = "GVAI_PRIVATE_WORKSPACE_KEY"
ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV = "GVAI_PRIVATE_WORKSPACE_AUDIT_DIR"
FILESYSTEM_SANDBOX_READ_PATHS_ENV = "GVAI_PRIVATE_SANDBOX_READ_PATHS"

_SANDBOXED_ENCRYPTED_WORKER = (
    "/app/privacy/encrypted_private_model_worker.py"
)

# Defense-in-depth: even if a future edit widens _LOCAL_MODEL_CONFIG_ENV by
# mistake, none of these may ever be handed to the worker through extra_env.
_FORBIDDEN_EXTRA_ENV_NAMES = frozenset(
    {
        ENCRYPTED_WORKSPACE_KEY_ENV,
        ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV,
        FILESYSTEM_SANDBOX_READ_PATHS_ENV,
        "GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND",
        "PYTHONPATH",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "DYLD_INSERT_LIBRARIES",
        "BASH_ENV",
        "ENV",
        "WORKER_ID",
        "PROJECT_ID",
        "AUTHORITY",
        "WORKSPACE_ROOT",
    }
    | EXTERNAL_SECRET_ENV
)

_ENCRYPTED_REQUEST_PATH = "request.json"
_ENCRYPTED_RESULT_PATH = "result.json"


def _flag(name: str, default: str = "0") -> bool:
    return (
        os.getenv(name, default)
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


def private_build_enabled() -> bool:
    return _flag("GVAI_PRIVATE_BUILD_MODE")


def encrypted_workspace_enabled() -> bool:
    return _flag("GVAI_PRIVATE_ENCRYPTED_WORKSPACE")


def load_trusted_workspace_key(
    env_var: str = ENCRYPTED_WORKSPACE_KEY_ENV,
) -> bytes:
    """Load the 32-byte AES-GCM workspace key.

    This reference loader must run only in the trusted parent process --
    never inside the worker. It fails closed on any missing or malformed
    key rather than falling back to plaintext or an external model.

    Reading a raw secret from process environment is a development-grade
    convenience only. Production deployments should replace this loader
    with a call to a real secret manager (e.g. a cloud KMS/Vault-backed
    provider) that never places the key in process environment at all.
    """

    raw = os.environ.get(env_var)

    if raw is None or not raw.strip():
        raise RuntimeError(
            "GVAI encrypted workspace key is missing. "
            f"Set {env_var}."
        )

    try:
        key = base64.b64decode(raw.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError(
            "GVAI encrypted workspace key is not valid base64."
        ) from exc

    if len(key) != 32:
        raise RuntimeError(
            "GVAI encrypted workspace key must decode to exactly "
            "32 bytes."
        )

    return key


def _private_worker_command(
    command: Optional[str] = None,
) -> list[str]:
    raw = (
        command
        or os.getenv(
            "GVAI_PRIVATE_MODEL_COMMAND"
        )
        or ""
    ).strip()

    if not raw:
        raise RuntimeError(
            "GVAI Private Build Mode requires "
            "GVAI_PRIVATE_MODEL_COMMAND."
        )

    parts = shlex.split(raw)

    if not parts:
        raise RuntimeError(
            "GVAI_PRIVATE_MODEL_COMMAND is empty."
        )

    return parts


def _private_worker_env() -> Dict[str, str]:
    env = os.environ.copy()

    for key in EXTERNAL_SECRET_ENV:
        env.pop(key, None)

    env[
        "GVAI_PRIVATE_BUILD_MODE"
    ] = "1"

    env[
        "GVAI_NETWORK_ISOLATED"
    ] = "1"

    return env


def _encrypted_worker_command() -> list[str]:
    raw = (
        os.getenv("GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND") or ""
    ).strip()

    if not raw:
        return [sys.executable, _SANDBOXED_ENCRYPTED_WORKER]

    parts = shlex.split(raw)

    if not parts:
        raise RuntimeError(
            "GVAI_PRIVATE_ENCRYPTED_WORKER_COMMAND is empty."
        )

    # This selects only the worker command run inside the mandatory
    # Bubblewrap boundary. The trusted parent constructs that boundary
    # separately, so this override cannot replace or bypass it.
    return parts


def _normalize_local_model_command(raw: str) -> str:
    """Use the canonical interpreter path inside the private namespace."""

    try:
        parts = shlex.split(raw)
    except ValueError:
        raise RuntimeError(
            "GVAI private model worker configuration is invalid."
        ) from None

    if not parts:
        raise RuntimeError(
            "GVAI private model worker configuration is invalid."
        )

    executable = Path(parts[0])
    if executable.is_absolute():
        try:
            configured = executable.resolve(strict=True)
            current = Path(sys.executable).resolve(strict=True)
        except OSError:
            pass
        else:
            if configured == current:
                parts[0] = str(current)

    return shlex.join(parts)


def _filesystem_sandbox_read_paths() -> list[Path]:
    """Return operator-approved, read-only model and worker assets."""

    raw = os.getenv(FILESYSTEM_SANDBOX_READ_PATHS_ENV, "")
    if not raw:
        return []

    values = raw.split(os.pathsep)
    if any(not value.strip() for value in values):
        raise RuntimeError(
            "GVAI private filesystem sandbox configuration is invalid."
        )

    return [Path(value.strip()) for value in values]


def _local_model_extra_env() -> Dict[str, str]:
    """Build the narrow, fixed-allowlist config the worker needs.

    Only the exact names in _LOCAL_MODEL_CONFIG_ENV are ever considered,
    and each is additionally checked against a forbidden-name denylist as
    defense-in-depth. No key, credential, identity, authority, or path
    value can reach the worker through this channel.
    """

    local_model_env: Dict[str, str] = {}

    for name in _LOCAL_MODEL_CONFIG_ENV:
        if name not in os.environ:
            continue
        if name in _FORBIDDEN_EXTRA_ENV_NAMES:
            raise RuntimeError(
                "GVAI private model worker configuration is invalid."
            )
        value = os.environ[name]
        if name == "GVAI_LOCAL_MODEL_COMMAND":
            value = _normalize_local_model_command(value)
        local_model_env[name] = value

    return local_model_env


def run_private_model_encrypted_workspace(
    system_prompt: str,
    user_content: str,
    *,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    """Encrypted-workspace execution path for Private Build Mode.

    The trusted parent (this function) owns the AES-GCM key, the control
    plane, and worker/project identity for the lifetime of this single
    request. It seals the request into a per-request encrypted workspace,
    execs a network-isolated worker that can reach that workspace only
    through WorkspaceClient, and opens the sealed result itself. The
    worker never receives the key, the control plane, the workspace root
    path, raw identity strings, or any external-model credential.
    """

    # Fail closed before anything is spawned or written if configuration
    # is missing/malformed -- never fall back to plaintext or external.
    key = load_trusted_workspace_key()

    worker_id = uuid.uuid4().hex
    project_id = uuid.uuid4().hex

    audit_dir = Path(
        os.getenv(ENCRYPTED_WORKSPACE_AUDIT_DIR_ENV)
        or (Path(tempfile.gettempdir()) / "gvai-private-workspace-audit")
    )

    authority = WorkspaceAuthority(frozenset({"read", "write"}))

    storage_dir = Path(tempfile.mkdtemp(prefix="gvai-private-ws-"))
    try:
        control_plane = AESGCMControlPlane(
            key,
            lambda request, _wid=worker_id, _pid=project_id: (
                request.worker_id == _wid and request.project_id == _pid
            ),
        )
        adapter = EncryptedProjectWorkspace(
            storage_dir,
            control_plane,
            WorkspaceAuditLog(audit_dir / "audit.jsonl"),
        )

        request_bytes = json.dumps(
            {
                "system_prompt": system_prompt,
                "user_content": user_content,
            }
        ).encode("utf-8")

        try:
            adapter.execute(
                WorkspaceRequest(
                    worker_id,
                    project_id,
                    "write",
                    _ENCRYPTED_REQUEST_PATH,
                ),
                authority,
                request_bytes,
            )
        except Exception:
            raise RuntimeError(
                "GVAI private model worker failed."
            ) from None

        broker = WorkspaceBroker(
            adapter,
            worker_id=worker_id,
            project_id=project_id,
            authority=authority,
        )

        local_model_env = _local_model_extra_env()

        try:
            sandbox_command = build_filesystem_sandbox_command(
                _encrypted_worker_command(),
                worker_environment=local_model_env,
                read_only_paths=_filesystem_sandbox_read_paths(),
                denied_paths=(
                    ROOT,
                    storage_dir,
                    audit_dir,
                ),
            )
            broker.run_worker(
                sandbox_command,
                timeout=timeout,
            )
        except (FilesystemSandboxError, WorkspaceWorkerError):
            raise RuntimeError(
                "GVAI private model worker failed."
            ) from None

        try:
            result_bytes = adapter.execute(
                WorkspaceRequest(
                    worker_id,
                    project_id,
                    "read",
                    _ENCRYPTED_RESULT_PATH,
                ),
                authority,
            )
        except Exception:
            raise RuntimeError(
                "GVAI private model worker failed."
            ) from None
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)

    try:
        response = json.loads((result_bytes or b"").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RuntimeError(
            "GVAI private model worker returned invalid JSON."
        ) from None

    reply = response.get("reply")

    if not isinstance(reply, str):
        raise RuntimeError(
            "GVAI private model worker "
            "response is missing reply."
        )

    model = response.get("model") or "private-local"

    return {
        "provider": "local",
        "model": str(model),
        "reply": reply,
        "network_isolated": True,
    }


def run_private_model(
    system_prompt: str,
    user_content: str,
    *,
    command: Optional[str] = None,
    timeout: float = 120.0,
) -> Dict[str, Any]:
    if not private_build_enabled():
        raise RuntimeError(
            "Private runtime requested while "
            "GVAI_PRIVATE_BUILD_MODE is disabled."
        )

    if encrypted_workspace_enabled():
        return run_private_model_encrypted_workspace(
            system_prompt,
            user_content,
            timeout=timeout,
        )

    if not SANDBOX.exists():
        raise RuntimeError(
            "GVAI private network sandbox "
            "is unavailable."
        )

    worker_command = (
        _private_worker_command(command)
    )

    request_payload = {
        "system_prompt": system_prompt,
        "user_content": user_content,
    }

    result = subprocess.run(
        [
            str(SANDBOX),
            *worker_command,
        ],
        cwd=ROOT,
        env=_private_worker_env(),
        input=json.dumps(
            request_payload
        ),
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "GVAI private model worker failed. "
            f"exit={result.returncode}; "
            f"stderr={result.stderr.strip()}"
        )

    raw_output = (
        result.stdout.strip()
    )

    if not raw_output:
        raise RuntimeError(
            "GVAI private model worker "
            "returned no output."
        )

    try:
        response = json.loads(
            raw_output.splitlines()[-1]
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "GVAI private model worker "
            "returned invalid JSON."
        ) from exc

    reply = response.get("reply")

    if not isinstance(reply, str):
        raise RuntimeError(
            "GVAI private model worker "
            "response is missing reply."
        )

    model = (
        response.get("model")
        or "private-local"
    )

    return {
        "provider": "local",
        "model": str(model),
        "reply": reply,
        "network_isolated": True,
    }
