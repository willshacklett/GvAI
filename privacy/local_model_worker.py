"""
GVAI local-model worker.

This process is intended to run *inside* the GVAI network sandbox.

Input on stdin:
{
    "system_prompt": "...",
    "user_content": "..."
}

The actual local inference engine is configured with:

    GVAI_LOCAL_MODEL_COMMAND

The configured command receives the completed prompt on stdin and must
return model text on stdout.

No shell is used. No external model fallback exists.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from typing import Any, Dict


def _read_request() -> Dict[str, Any]:
    raw = sys.stdin.read()

    if not raw.strip():
        raise RuntimeError(
            "GVAI local-model worker received no input."
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "GVAI local-model worker received invalid JSON."
        ) from exc

    system_prompt = payload.get("system_prompt", "")
    user_content = payload.get("user_content")

    if not isinstance(system_prompt, str):
        raise RuntimeError(
            "system_prompt must be a string."
        )

    if not isinstance(user_content, str):
        raise RuntimeError(
            "user_content must be a string."
        )

    return {
        "system_prompt": system_prompt,
        "user_content": user_content,
    }


def _model_command() -> list[str]:
    raw = os.getenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        "",
    ).strip()

    if not raw:
        raise RuntimeError(
            "GVAI_LOCAL_MODEL_COMMAND is required."
        )

    command = shlex.split(raw)

    if not command:
        raise RuntimeError(
            "GVAI_LOCAL_MODEL_COMMAND is empty."
        )

    return command


def _build_prompt(
    system_prompt: str,
    user_content: str,
) -> str:
    if system_prompt.strip():
        return (
            f"System:\n{system_prompt.strip()}\n\n"
            f"User:\n{user_content.strip()}\n\n"
            "Assistant:\n"
        )

    return (
        f"User:\n{user_content.strip()}\n\n"
        "Assistant:\n"
    )


def run_local_model() -> Dict[str, Any]:
    request = _read_request()
    command = _model_command()

    prompt = _build_prompt(
        request["system_prompt"],
        request["user_content"],
    )

    timeout = float(
        os.getenv(
            "GVAI_LOCAL_MODEL_TIMEOUT",
            "120",
        )
    )

    result = subprocess.run(
        command,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Local model command failed. "
            f"exit={result.returncode}; "
            f"stderr={result.stderr.strip()}"
        )

    reply = result.stdout.strip()

    if not reply:
        raise RuntimeError(
            "Local model command returned no output."
        )

    return {
        "model": os.getenv(
            "GVAI_LOCAL_MODEL_NAME",
            "gvai-local",
        ),
        "reply": reply,
    }


def main() -> int:
    try:
        response = run_local_model()
    except Exception as exc:
        print(
            f"GVAI local-model worker error: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            response,
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
