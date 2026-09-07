import pytest

import gvai.ai_bridge as bridge


def _must_not_transmit(*args, **kwargs):
    raise AssertionError(
        "NETWORK TRANSMISSION OCCURRED — PRIVACY GATE FAILED"
    )


@pytest.mark.parametrize(
    "provider,function,key_name",
    [
        ("openai", bridge.chat_openai, "OPENAI_API_KEY"),
        ("xai", bridge.chat_xai, "XAI_API_KEY"),
        (
            "anthropic",
            bridge.chat_anthropic,
            "ANTHROPIC_API_KEY",
        ),
    ],
)
def test_private_build_mode_blocks_before_network(
    monkeypatch,
    provider,
    function,
    key_name,
):
    monkeypatch.setenv(key_name, "fake-key")
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_DATA_CLASS", "private")

    monkeypatch.setattr(
        bridge.requests,
        "post",
        _must_not_transmit,
    )

    with pytest.raises(PermissionError):
        function(
            "This is private GVAI project information."
        )


def test_normal_mode_reaches_network_layer(monkeypatch):
    """
    We don't actually contact OpenAI.

    This proves that when Private Build Mode is OFF, the privacy
    guard allows GVAI to proceed to its normal network layer.
    """

    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "0")
    monkeypatch.delenv("GVAI_DATA_CLASS", raising=False)

    reached_network = {"value": False}

    def fake_post(*args, **kwargs):
        reached_network["value"] = True
        raise RuntimeError("fake-network-stop")

    monkeypatch.setattr(
        bridge.requests,
        "post",
        fake_post,
    )

    with pytest.raises(
        RuntimeError,
        match="fake-network-stop",
    ):
        bridge.chat_openai("ordinary GVAI request")

    assert reached_network["value"] is True


def test_explicit_share_can_reach_network(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv(
        "GVAI_DATA_CLASS",
        "explicitly_shared",
    )
    monkeypatch.setenv(
        "GVAI_CONSENT_TOKEN",
        "test-consent",
    )

    reached_network = {"value": False}

    def fake_post(*args, **kwargs):
        reached_network["value"] = True
        raise RuntimeError("fake-network-stop")

    monkeypatch.setattr(
        bridge.requests,
        "post",
        fake_post,
    )

    with pytest.raises(
        RuntimeError,
        match="fake-network-stop",
    ):
        bridge.chat_openai(
            "User deliberately approved this information."
        )

    assert reached_network["value"] is True
