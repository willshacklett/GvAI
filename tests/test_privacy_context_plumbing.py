import pytest

from privacy.router import DataClass, PrivacyContext


def private_context():
    return PrivacyContext(
        user_id="user-1",
        project_id="secret-project",
        data_class=DataClass.PRIVATE,
        private_build_mode=True,
    )


def public_context():
    return PrivacyContext(
        user_id="user-1",
        project_id="public-project",
        data_class=DataClass.PUBLIC,
        private_build_mode=False,
    )


def test_llm_explicit_private_context_blocks(monkeypatch):
    import gvai.llm as mod

    monkeypatch.setattr(mod, "llm_available", lambda: True)

    class FakeCompletions:
        @staticmethod
        def create(*args, **kwargs):
            raise AssertionError(
                "External SDK call must not be reached"
            )

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
        mod.generate_llm_response(
            "secret",
            privacy_context=private_context(),
        )


def test_llm_explicit_public_context_can_reach_provider(monkeypatch):
    import gvai.llm as mod

    monkeypatch.setattr(mod, "llm_available", lambda: True)

    # Deliberately set hostile env values. Explicit context should
    # remain authoritative inside the already-resolved call.
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_DATA_CLASS", "private")

    class Message:
        content = "OK"

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    class FakeCompletions:
        @staticmethod
        def create(*args, **kwargs):
            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        mod,
        "OpenAI",
        lambda *a, **k: FakeClient(),
    )

    result = mod.generate_llm_response(
        "public information",
        privacy_context=public_context(),
    )

    assert result == "OK"


def test_gateway_explicit_private_context_blocks(monkeypatch):
    import gateway.app as mod

    monkeypatch.setenv(
        "OPENAI_COMPAT_BASE_URL",
        "https://example.invalid",
    )
    monkeypatch.setenv(
        "OPENAI_COMPAT_API_KEY",
        "test-key",
    )

    def network_tripwire(*args, **kwargs):
        raise AssertionError(
            "Network transmission must not be reached"
        )

    monkeypatch.setattr(
        mod.requests,
        "post",
        network_tripwire,
    )

    with pytest.raises(PermissionError):
        mod.call_openai_compatible(
            "secret",
            None,
            None,
            privacy_context=private_context(),
        )


def test_gateway_explicit_public_context_can_reach_provider(monkeypatch):
    import gateway.app as mod

    monkeypatch.setenv(
        "OPENAI_COMPAT_BASE_URL",
        "https://example.invalid",
    )
    monkeypatch.setenv(
        "OPENAI_COMPAT_API_KEY",
        "test-key",
    )

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "OK"
                        }
                    }
                ]
            }

    monkeypatch.setattr(
        mod.requests,
        "post",
        lambda *a, **k: FakeResponse(),
    )

    result = mod.call_openai_compatible(
        "public information",
        None,
        None,
        privacy_context=public_context(),
    )

    assert result == "OK"
