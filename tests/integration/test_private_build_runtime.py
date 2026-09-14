from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_model_router_uses_network_isolated_private_worker(
    monkeypatch,
    tmp_path,
):
    worker = (
        tmp_path
        / "fake_private_model.py"
    )

    worker.write_text(
        r'''
import json
import os
import socket
import sys


request = json.loads(
    sys.stdin.read()
)

assert (
    os.environ[
        "GVAI_PRIVATE_BUILD_MODE"
    ]
    == "1"
)

assert (
    os.environ[
        "GVAI_NETWORK_ISOLATED"
    ]
    == "1"
)

# External model credentials must
# not enter the private worker.
assert (
    "OPENAI_API_KEY"
    not in os.environ
)

assert (
    "ANTHROPIC_API_KEY"
    not in os.environ
)

# The worker itself must have no
# external route.
try:
    socket.create_connection(
        ("1.1.1.1", 443),
        timeout=1,
    )
except OSError:
    pass
else:
    raise AssertionError(
        "private worker escaped "
        "network sandbox"
    )


print(json.dumps({
    "model":
        "gvai-private-test-model",
    "reply":
        (
            "PRIVATE:"
            + request["user_content"]
        ),
}))
''',
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "GVAI_PRIVATE_BUILD_MODE",
        "1",
    )

    monkeypatch.setenv(
        "GVAI_DATA_CLASS",
        "private",
    )

    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "must-not-enter-worker",
    )

    monkeypatch.setenv(
        "ANTHROPIC_API_KEY",
        "must-not-enter-worker",
    )

    monkeypatch.setenv(
        "GVAI_PRIVATE_MODEL_COMMAND",
        (
            f"{sys.executable} "
            f"{worker}"
        ),
    )

    import gvai.model_router as mod

    class ForbiddenOpenAI:
        def __init__(
            self,
            *args,
            **kwargs,
        ):
            raise AssertionError(
                "OpenAI client must not be "
                "constructed in Private "
                "Build Mode."
            )

    monkeypatch.setattr(
        mod,
        "OpenAI",
        ForbiddenOpenAI,
    )

    result = mod.call_model(
        "private system",
        "private invention",
    )

    assert (
        result["provider"]
        == "local"
    )

    assert (
        result["model"]
        == "gvai-private-test-model"
    )

    assert (
        result["reply"]
        == "PRIVATE:private invention"
    )

    assert (
        result["network_isolated"]
        is True
    )


def test_private_runtime_fails_closed_without_worker(
    monkeypatch,
):
    monkeypatch.setenv(
        "GVAI_PRIVATE_BUILD_MODE",
        "1",
    )

    monkeypatch.delenv(
        "GVAI_PRIVATE_MODEL_COMMAND",
        raising=False,
    )

    import gvai.model_router as mod

    with pytest.raises(
        RuntimeError,
        match=(
            "GVAI_PRIVATE_MODEL_COMMAND"
        ),
    ):
        mod.call_model(
            "system",
            "PRIVATE",
        )


def test_model_router_keeps_external_path_when_private_mode_disabled(
    monkeypatch,
):
    monkeypatch.setenv(
        "GVAI_PRIVATE_BUILD_MODE",
        "0",
    )
    monkeypatch.setenv(
        "GVAI_PROVIDER",
        "openai",
    )
    monkeypatch.setenv(
        "GVAI_DATA_CLASS",
        "public",
    )
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "fake-key",
    )

    import gvai.model_router as mod

    class FakeMessage:
        content = "normal external path"

    class FakeChoice:
        message = FakeMessage()

    class FakeCompletion:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(
            self,
            *args,
            **kwargs,
        ):
            return FakeCompletion()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        mod,
        "OpenAI",
        lambda *a, **k: FakeClient(),
    )

    result = mod.call_model(
        "system",
        "public request",
    )

    assert result["provider"] == "openai"
    assert (
        result["reply"]
        == "normal external path"
    )
