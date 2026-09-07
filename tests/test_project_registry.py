import json

import pytest

from privacy.project_policy import ProjectPrivacyMode
from privacy.project_registry import (
    ProjectPolicyRegistry,
    authoritative_project_policy,
)


def test_unknown_project_fails_closed(tmp_path):
    registry = ProjectPolicyRegistry(str(tmp_path / "projects.json"))

    policy = registry.get_policy(
        user_id="alice",
        project_id="unknown",
    )

    assert policy.mode == ProjectPrivacyMode.PRIVATE


def test_known_modes(tmp_path):
    path = tmp_path / "projects.json"

    path.write_text(json.dumps({
        "version": 1,
        "projects": {
            "secret": {"privacy_mode": "private"},
            "research": {"privacy_mode": "public_data_only"},
            "normal": {"privacy_mode": "standard"},
        },
    }))

    registry = ProjectPolicyRegistry(str(path))

    assert registry.get_policy(
        user_id="alice",
        project_id="secret",
    ).mode == ProjectPrivacyMode.PRIVATE

    assert registry.get_policy(
        user_id="alice",
        project_id="research",
    ).mode == ProjectPrivacyMode.PUBLIC_DATA_ONLY

    assert registry.get_policy(
        user_id="alice",
        project_id="normal",
    ).mode == ProjectPrivacyMode.STANDARD


def test_invalid_stored_mode_fails_closed(tmp_path):
    path = tmp_path / "projects.json"

    path.write_text(json.dumps({
        "version": 1,
        "projects": {
            "secret": {
                "privacy_mode": "TURN_PRIVACY_OFF"
            }
        },
    }))

    registry = ProjectPolicyRegistry(str(path))

    assert registry.get_policy(
        user_id="alice",
        project_id="secret",
    ).mode == ProjectPrivacyMode.PRIVATE


def test_corrupt_registry_fails_closed(tmp_path):
    path = tmp_path / "projects.json"
    path.write_text("{ broken json")

    registry = ProjectPolicyRegistry(str(path))

    assert registry.get_policy(
        user_id="alice",
        project_id="secret",
    ).mode == ProjectPrivacyMode.PRIVATE


def test_set_policy_persists(tmp_path):
    path = tmp_path / "projects.json"
    registry = ProjectPolicyRegistry(str(path))

    registry.set_policy(
        project_id="research",
        privacy_mode="public_data_only",
    )

    reloaded = ProjectPolicyRegistry(str(path))

    assert reloaded.get_policy(
        user_id="alice",
        project_id="research",
    ).mode == ProjectPrivacyMode.PUBLIC_DATA_ONLY


def test_invalid_admin_write_rejected(tmp_path):
    registry = ProjectPolicyRegistry(str(tmp_path / "projects.json"))

    with pytest.raises(ValueError):
        registry.set_policy(
            project_id="secret",
            privacy_mode="disable_everything",
        )


def test_authoritative_resolver(tmp_path):
    path = tmp_path / "projects.json"
    registry = ProjectPolicyRegistry(str(path))

    registry.set_policy(
        project_id="secret",
        privacy_mode="private",
    )

    policy = authoritative_project_policy(
        user_id="alice",
        project_id="secret",
        registry=registry,
    )

    assert policy.mode == ProjectPrivacyMode.PRIVATE
