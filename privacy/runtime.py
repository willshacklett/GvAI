"""
GVAI Private Build Runtime.

Private Build Mode executes model work through the network-isolated
sandbox. External model credentials are stripped from the worker
environment.

Worker protocol:

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
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
from typing import Dict, Any, Optional


ROOT = Path(__file__).resolve().parents[1]

SANDBOX = (
    ROOT
    / "privacy"
    / "run_network_sandbox.sh"
)

EXTERNAL_SECRET_ENV = {
    "OPENAI_API_KEY",
    "OPENAI_COMPAT_API_KEY",
    "ANTHROPIC_API_KEY",
    "GROK_API_KEY",
    "XAI_API_KEY",
}


def private_build_enabled() -> bool:
    return (
        os.getenv(
            "GVAI_PRIVATE_BUILD_MODE",
            "0",
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


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
