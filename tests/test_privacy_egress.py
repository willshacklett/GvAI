import pytest

from privacy.egress import (
    authorize_external_model,
    authorize_world_read,
)


def test_private_project_blocks_openai(monkeypatch, tmp_path):
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_DATA_CLASS", "private")
    monkeypatch.setenv("GVAI_USER_ID", "alice")
    monkeypatch.setenv("GVAI_PROJECT_ID", "secret-project")

    with pytest.raises(PermissionError):
        authorize_external_model(
            "private invention",
            provider="openai",
        )


def test_private_project_blocks_anthropic(monkeypatch):
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_DATA_CLASS", "private")

    with pytest.raises(PermissionError):
        authorize_external_model(
            "private business plan",
            provider="anthropic",
        )


def test_private_project_blocks_xai(monkeypatch):
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_DATA_CLASS", "private")

    with pytest.raises(PermissionError):
        authorize_external_model(
            "private source code",
            provider="xai",
        )


def test_world_read_still_allowed(monkeypatch):
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv("GVAI_DATA_CLASS", "private")

    result = authorize_world_read(
        source="public-economic-data"
    )

    assert result["allowed"] is True


def test_explicit_share_can_leave(monkeypatch):
    monkeypatch.setenv("GVAI_PRIVATE_BUILD_MODE", "1")
    monkeypatch.setenv(
        "GVAI_DATA_CLASS",
        "explicitly_shared"
    )
    monkeypatch.setenv(
        "GVAI_CONSENT_TOKEN",
        "temporary-consent"
    )

    result = authorize_external_model(
        "user approved this text",
        provider="openai",
    )

    assert result["allowed"] is True
