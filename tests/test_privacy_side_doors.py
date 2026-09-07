import pytest


def block_sdk_call(*args, **kwargs):
    raise AssertionError(
        "EXTERNAL MODEL CALL REACHED — PRIVACY BYPASS DETECTED"
    )


def block_http_call(*args, **kwargs):
    raise AssertionError(
        "HTTP PROVIDER CALL REACHED — PRIVACY BYPASS DETECTED"
    )


def private_env(monkeypatch):
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_DATA_CLASS", "private")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv(
        "OPENAI_COMPAT_API_KEY",
        "fake-key",
    )
    monkeypatch.setenv(
        "OPENAI_COMPAT_BASE_URL",
        "https://example.invalid/v1",
    )


def test_model_router_blocked(monkeypatch):
    private_env(monkeypatch)

    import gvai.model_router as mod

    class FakeCompletions:
        create = staticmethod(block_sdk_call)

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        mod,
        "OpenAI",
        lambda *a, **k: FakeClient(),
    )

    with pytest.raises(PermissionError):
        mod.call_model("system", "PRIVATE")


def test_llm_blocked(monkeypatch):
    private_env(monkeypatch)

    import gvai.llm as mod

    class FakeCompletions:
        create = staticmethod(block_sdk_call)

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        mod,
        "OpenAI",
        lambda *a, **k: FakeClient(),
    )

    with pytest.raises(PermissionError):
        mod.generate_llm_response("PRIVATE")


def test_ai_gate_blocked(monkeypatch):
    """
    ai_gate.py is legacy code with a missing GVMemoryGate dependency,
    so importing the entire module is impossible independently of
    privacy.

    Verify structurally that its external model call is guarded,
    while executable provider paths are covered by runtime tripwires
    elsewhere in this suite.
    """
    from pathlib import Path

    source = Path("gvai/api/ai_gate.py").read_text()

    guard = source.index(
        "authorize_external_model("
    )
    external_call = source.index(
        "client.chat.completions.create("
    )

    assert guard < external_call

def test_live_api_blocked(monkeypatch):
    private_env(monkeypatch)

    import openai

    class FakeCompletions:
        create = staticmethod(block_sdk_call)

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        openai,
        "OpenAI",
        lambda *a, **k: FakeClient(),
    )

    import gvai.live_api as mod

    monkeypatch.setattr(
        mod,
        "needs_web",
        lambda msg: False,
    )

    monkeypatch.setattr(
        mod,
        "grounding_packet",
        lambda msg: {
            "grounded": False,
            "context": "",
            "sources": [],
        },
    )

    client = mod.app.test_client()

    response = client.post(
        "/api/chat",
        json={"message": "PRIVATE"},
    )

    assert response.status_code == 403

    data = response.get_json()

    assert data["ok"] is False
    assert data["blocked"] is True
    assert data["reason"] == "privacy_policy"

def test_gateway_blocked(monkeypatch):
    private_env(monkeypatch)

    import gateway.app as mod

    monkeypatch.setattr(
        mod.requests,
        "post",
        block_http_call,
    )

    with pytest.raises(PermissionError):
        mod.call_openai_compatible(
            "PRIVATE",
            None,
            None,
        )
