from __future__ import annotations

import json

from privacy import configured_model_verification as verification


def test_verifier_executes_protected_runtime_without_exposing_reply(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        verification.runtime,
        "private_build_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        verification.runtime,
        "encrypted_workspace_enabled",
        lambda: True,
    )

    def fake_run(system_prompt, user_content, *, timeout):
        calls.append((system_prompt, user_content, timeout))
        return {
            "provider": "local",
            "model": "secret-model-name",
            "reply": "secret model reply",
            "network_isolated": True,
        }

    monkeypatch.setattr(
        verification.runtime,
        "run_private_model",
        fake_run,
    )

    report = verification.verify_configured_model_execution(timeout=7.0)

    assert report == {
        "scope": "configured_model_execution",
        "configured_model_execution": "pass",
        "production_ready": False,
    }
    assert len(calls) == 1
    assert calls[0][2] == 7.0

    serialized = json.dumps(report)
    assert "secret model reply" not in serialized
    assert "secret-model-name" not in serialized


def test_verifier_fails_closed_when_private_mode_is_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        verification.runtime,
        "private_build_enabled",
        lambda: False,
    )

    def must_not_run(*args, **kwargs):
        raise AssertionError("runtime must not execute")

    monkeypatch.setattr(
        verification.runtime,
        "run_private_model",
        must_not_run,
    )

    report = verification.verify_configured_model_execution()

    assert report["configured_model_execution"] == "fail"
    assert report["production_ready"] is False


def test_verifier_fails_closed_without_encrypted_workspace(
    monkeypatch,
):
    monkeypatch.setattr(
        verification.runtime,
        "private_build_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        verification.runtime,
        "encrypted_workspace_enabled",
        lambda: False,
    )

    def must_not_run(*args, **kwargs):
        raise AssertionError("runtime must not execute")

    monkeypatch.setattr(
        verification.runtime,
        "run_private_model",
        must_not_run,
    )

    report = verification.verify_configured_model_execution()

    assert report["configured_model_execution"] == "fail"
    assert report["production_ready"] is False


def test_verifier_sanitizes_runtime_failure(
    monkeypatch,
):
    monkeypatch.setattr(
        verification.runtime,
        "private_build_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        verification.runtime,
        "encrypted_workspace_enabled",
        lambda: True,
    )

    def fail_with_sensitive_text(*args, **kwargs):
        raise RuntimeError(
            "SECRET=/private/model/path operator-command sensitive-value"
        )

    monkeypatch.setattr(
        verification.runtime,
        "run_private_model",
        fail_with_sensitive_text,
    )

    report = verification.verify_configured_model_execution()

    serialized = json.dumps(report)
    assert report["configured_model_execution"] == "fail"
    assert report["production_ready"] is False
    assert "SECRET" not in serialized
    assert "/private/model/path" not in serialized
    assert "operator-command" not in serialized
    assert "sensitive-value" not in serialized


def test_verifier_rejects_nonlocal_or_unisolated_result(
    monkeypatch,
):
    monkeypatch.setattr(
        verification.runtime,
        "private_build_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        verification.runtime,
        "encrypted_workspace_enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        verification.runtime,
        "run_private_model",
        lambda *args, **kwargs: {
            "provider": "external",
            "reply": "unexpected",
            "network_isolated": True,
        },
    )

    report = verification.verify_configured_model_execution()
    assert report["configured_model_execution"] == "fail"

    monkeypatch.setattr(
        verification.runtime,
        "run_private_model",
        lambda *args, **kwargs: {
            "provider": "local",
            "reply": "unexpected",
            "network_isolated": False,
        },
    )

    report = verification.verify_configured_model_execution()
    assert report["configured_model_execution"] == "fail"
