"""
GVAI llama.cpp local inference adapter.

Runs llama.cpp's llama-cli process using a local GGUF model.

This adapter is intended to be launched by:

    privacy/local_model_worker.py

inside the GVAI network sandbox.

Input:
    completed prompt on stdin

Output:
    generated model text on stdout

Required environment:
    GVAI_LLAMA_CPP_BIN
    GVAI_LOCAL_MODEL_PATH

Optional environment:
    GVAI_LOCAL_MAX_TOKENS
    GVAI_LOCAL_TEMPERATURE
    GVAI_LOCAL_CONTEXT_SIZE
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def _required_path(
    env_name: str,
    *,
    executable: bool = False,
) -> Path:
    raw = os.getenv(
        env_name,
        "",
    ).strip()

    if not raw:
        raise RuntimeError(
            f"{env_name} is required."
        )

    path = Path(raw).expanduser()

    if not path.exists():
        raise RuntimeError(
            f"{env_name} does not exist: {path}"
        )

    if executable and not os.access(
        path,
        os.X_OK,
    ):
        raise RuntimeError(
            f"{env_name} is not executable: {path}"
        )

    return path


def _positive_int(
    env_name: str,
    default: str,
) -> int:
    raw = os.getenv(
        env_name,
        default,
    )

    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"{env_name} must be an integer."
        ) from exc

    if value <= 0:
        raise RuntimeError(
            f"{env_name} must be greater than zero."
        )

    return value


def _temperature() -> float:
    raw = os.getenv(
        "GVAI_LOCAL_TEMPERATURE",
        "0.2",
    )

    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(
            "GVAI_LOCAL_TEMPERATURE "
            "must be numeric."
        ) from exc

    if value < 0:
        raise RuntimeError(
            "GVAI_LOCAL_TEMPERATURE "
            "must not be negative."
        )

    return value


def _extract_model_reply(output: str) -> str:
    text = output.strip()

    if "Assistant:" in text:
        text = text.rsplit(
            "Assistant:",
            1,
        )[1]

    if "Exiting..." in text:
        text = text.split(
            "Exiting...",
            1,
        )[0]

    return text.strip()


def run() -> str:
    prompt = sys.stdin.read()

    if not prompt.strip():
        raise RuntimeError(
            "llama.cpp adapter received no prompt."
        )

    binary = _required_path(
        "GVAI_LLAMA_CPP_BIN",
        executable=True,
    )

    model = _required_path(
        "GVAI_LOCAL_MODEL_PATH",
    )

    max_tokens = _positive_int(
        "GVAI_LOCAL_MAX_TOKENS",
        "512",
    )

    context_size = _positive_int(
        "GVAI_LOCAL_CONTEXT_SIZE",
        "4096",
    )

    temperature = _temperature()

    command = [
        str(binary),
        "-m",
        str(model),
        "-p",
        prompt,
        "-n",
        str(max_tokens),
        "-c",
        str(context_size),
        "--temp",
        str(temperature),
        "--no-display-prompt",
        "--single-turn",
        "--simple-io",
        "--log-disable",
        "--no-show-timings",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "llama.cpp inference failed. "
            f"exit={result.returncode}; "
            f"stderr={result.stderr.strip()}"
        )

    reply = _extract_model_reply(
        result.stdout
    )

    if not reply:
        raise RuntimeError(
            "llama.cpp returned no model output."
        )

    return reply


def main() -> int:
    try:
        reply = run()
    except Exception as exc:
        print(
            f"GVAI llama.cpp adapter error: {exc}",
            file=sys.stderr,
        )
        return 1

    print(reply)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
