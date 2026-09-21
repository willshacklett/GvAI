"""
GVAI encrypted-workspace private-model worker.

This process runs *inside* the GVAI network sandbox, exec-started by the
trusted ``WorkspaceBroker`` (see privacy/encrypted_workspace.py and
privacy/runtime.py). Unlike privacy/local_model_worker.py, it never
receives the request/response on stdin/stdout directly: those pipes are
already claimed by the WorkspaceBroker protocol. Instead it uses
WorkspaceClient to read its request and write its result through the
broker, which is the only thing it can reach.

This worker receives no encryption key, no authority object, no trusted
callable, no workspace root path, no raw project/worker identity, and no
external-model credential. It only knows two logical file names inside
its authorized workspace.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the repository root is importable regardless of the working
# directory or PYTHONPATH the broker execs this worker with.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from privacy.local_model_worker import call_local_model
from privacy.workspace_worker_client import WorkspaceClient

REQUEST_PATH = "request.json"
RESULT_PATH = "result.json"


def run() -> None:
    client = WorkspaceClient()

    raw = client.read_bytes(REQUEST_PATH)
    request = json.loads(raw.decode("utf-8"))

    system_prompt = request.get("system_prompt")
    user_content = request.get("user_content")

    if not isinstance(system_prompt, str) or not isinstance(user_content, str):
        raise ValueError("invalid encrypted worker request")

    response = call_local_model(system_prompt, user_content)

    client.write_bytes(
        RESULT_PATH,
        json.dumps(response, ensure_ascii=False).encode("utf-8"),
    )


def main() -> int:
    try:
        run()
    except Exception:
        # No plaintext, path, or exception detail leaves this process:
        # stderr is discarded by the broker and the non-zero exit is the
        # only signal the trusted parent receives.
        print("gvai encrypted worker failed", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
