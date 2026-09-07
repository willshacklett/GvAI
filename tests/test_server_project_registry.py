import json


def test_server_unknown_project_fails_closed(monkeypatch, tmp_path):
    import server.main as mod

    registry_path = tmp_path / "projects.json"

    monkeypatch.setenv(
        "GVAI_PROJECT_REGISTRY",
        str(registry_path),
    )
    monkeypatch.setenv(
        "GVAI_PROJECT_ID",
        "unknown-project",
    )
    monkeypatch.setenv(
        "GVAI_USER_ID",
        "alice",
    )
    monkeypatch.delenv(
        "GVAI_DATA_CLASS",
        raising=False,
    )

    ctx = mod.server_privacy_context()

    assert ctx.user_id == "alice"
    assert ctx.project_id == "unknown-project"
    assert ctx.private_build_mode is True
    assert ctx.data_class.value == "private"


def test_server_known_standard_project(monkeypatch, tmp_path):
    import server.main as mod

    registry_path = tmp_path / "projects.json"

    registry_path.write_text(json.dumps({
        "version": 1,
        "projects": {
            "normal": {
                "privacy_mode": "standard"
            }
        },
    }))

    monkeypatch.setenv(
        "GVAI_PROJECT_REGISTRY",
        str(registry_path),
    )
    monkeypatch.setenv(
        "GVAI_PROJECT_ID",
        "normal",
    )
    monkeypatch.setenv(
        "GVAI_USER_ID",
        "alice",
    )
    monkeypatch.delenv(
        "GVAI_DATA_CLASS",
        raising=False,
    )

    ctx = mod.server_privacy_context()

    assert ctx.user_id == "alice"
    assert ctx.project_id == "normal"
    assert ctx.private_build_mode is False
    assert ctx.data_class.value == "public"


def test_server_private_project_cannot_be_opened_by_env_class(
    monkeypatch,
    tmp_path,
):
    import server.main as mod

    registry_path = tmp_path / "projects.json"

    registry_path.write_text(json.dumps({
        "version": 1,
        "projects": {
            "secret": {
                "privacy_mode": "private"
            }
        },
    }))

    monkeypatch.setenv(
        "GVAI_PROJECT_REGISTRY",
        str(registry_path),
    )
    monkeypatch.setenv(
        "GVAI_PROJECT_ID",
        "secret",
    )
    monkeypatch.setenv(
        "GVAI_USER_ID",
        "alice",
    )
    monkeypatch.setenv(
        "GVAI_DATA_CLASS",
        "public",
    )

    ctx = mod.server_privacy_context()

    assert ctx.project_id == "secret"
    assert ctx.private_build_mode is True
    assert ctx.data_class.value == "public"
