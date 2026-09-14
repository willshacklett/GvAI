from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from privacy.runtime import run_private_model


def test_private_runtime_executes_local_model_worker(
    monkeypatch,
    tmp_path,
):
    fake_engine = tmp_path / "fake_local_engine.py"

    fake_engine.write_text(
        r'''
import sys

prompt = sys.stdin.read()

assert "System:" in prompt
assert "You are GVAI." in prompt
assert "User:" in prompt
assert "Keep this private." in prompt
assert "Assistant:" in prompt

print("local model reply")
''',
        encoding="utf-8",
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
            f"{fake_engine}"
        ),
    )

    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_NAME",
        "gvai-test-local",
    )

    result = run_private_model(
        "You are GVAI.",
        "Keep this private.",
    )

    assert result == {
        "provider": "local",
        "model": "gvai-test-local",
        "reply": "local model reply",
        "network_isolated": True,
    }


def test_local_model_worker_fails_closed_without_engine(
    monkeypatch,
):
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

    monkeypatch.delenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="private model worker failed",
    ):
        run_private_model(
            "system",
            "private request",
        )


def test_local_model_worker_output_protocol(
    monkeypatch,
    tmp_path,
):
    fake_engine = tmp_path / "engine.py"

    fake_engine.write_text(
        'print("hello from local inference")\n',
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_COMMAND",
        f"{sys.executable} {fake_engine}",
    )

    monkeypatch.setenv(
        "GVAI_LOCAL_MODEL_NAME",
        "local-test",
    )

    import subprocess

    request = {
        "system_prompt": "system",
        "user_content": "private",
    }

    result = subprocess.run(
        [
            sys.executable,
            "privacy/local_model_worker.py",
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0

    response = json.loads(
        result.stdout.strip()
    )

    assert response == {
        "model": "local-test",
        "reply": "hello from local inference",
    }
