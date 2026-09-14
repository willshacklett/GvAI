from __future__ import annotations

import json
from pathlib import Path
import stat
import sys

import pytest

from privacy.runtime import run_private_model


def _make_fake_llama(
    tmp_path: Path,
) -> Path:
    binary = tmp_path / "llama-cli"

    binary.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]

assert "-m" in args
assert "-p" in args
assert "-n" in args
assert "-c" in args
assert "--temp" in args
assert "--no-display-prompt" in args

prompt = args[
    args.index("-p") + 1
]

assert "System:" in prompt
assert "You are GVAI." in prompt
assert "User:" in prompt
assert "Private inference." in prompt
assert "Assistant:" in prompt

print("llama local reply")
""",
        encoding="utf-8",
    )

    binary.chmod(
        binary.stat().st_mode
        | stat.S_IXUSR
    )

    return binary


def test_private_runtime_reaches_llama_cpp_adapter(
    monkeypatch,
    tmp_path,
):
    binary = _make_fake_llama(
        tmp_path
    )

    model = tmp_path / "model.gguf"
    model.write_bytes(b"fake-gguf")

    monkeypatch.setenv(
        "GVAI_PRIVATE_BUILD_MODE",
        "1",
    )

    monkeypatch.setenv(
        "GVAI_PRIVATE_MODEL_COMMAND",
        (
            f"{sys.executable} "
            "privacy/local_model_worker.py"
        ),
    )

    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        (
            f"{sys.executable} "
            "privacy/llama_cpp_engine.py"
        ),
    )

    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_NAME",
        "gvai-llama-test",
    )

    monkeypatch.setenv(
        "GVAI_LLAMA_CPP_BIN",
        str(binary),
    )

    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_PATH",
        str(model),
    )

    result = run_private_model(
        "You are GVAI.",
        "Private inference.",
    )

    assert result == {
        "provider": "local",
        "model": "gvai-llama-test",
        "reply": "llama local reply",
        "network_isolated": True,
    }


def test_llama_adapter_fails_closed_without_binary(
    monkeypatch,
    tmp_path,
):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fake")

    monkeypatch.setenv(
        "GVAI_PRIVATE_BUILD_MODE",
        "1",
    )

    monkeypatch.setenv(
        "GVAI_PRIVATE_MODEL_COMMAND",
        (
            f"{sys.executable} "
            "privacy/local_model_worker.py"
        ),
    )

    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        (
            f"{sys.executable} "
            "privacy/llama_cpp_engine.py"
        ),
    )

    monkeypatch.delenv(
        "GVAI_LLAMA_CPP_BIN",
        raising=False,
    )

    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_PATH",
        str(model),
    )

    with pytest.raises(
        RuntimeError,
        match="private model worker failed",
    ):
        run_private_model(
            "system",
            "private",
        )


def test_llama_adapter_fails_closed_without_model(
    monkeypatch,
    tmp_path,
):
    binary = _make_fake_llama(
        tmp_path
    )

    monkeypatch.setenv(
        "GVAI_PRIVATE_BUILD_MODE",
        "1",
    )

    monkeypatch.setenv(
        "GVAI_PRIVATE_MODEL_COMMAND",
        (
            f"{sys.executable} "
            "privacy/local_model_worker.py"
        ),
    )

    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        (
            f"{sys.executable} "
            "privacy/llama_cpp_engine.py"
        ),
    )

    monkeypatch.setenv(
        "GVAI_LLAMA_CPP_BIN",
        str(binary),
    )

    monkeypatch.delenv(
        "GVAI_LOCAL_MODEL_PATH",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="private model worker failed",
    ):
        run_private_model(
            "system",
            "private",
        )
