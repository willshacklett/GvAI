from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import threading
import time

import pytest

from privacy.encrypted_workspace import (
    AESGCMControlPlane, EncryptedProjectWorkspace, WorkspaceAuditError,
    WorkspaceAuditLog, WorkspaceAuthority, WorkspaceBroker,
)
from privacy.external_model_authority import (
    ApprovalBinding,
    TrustedExternalModelAuthority,
)
from privacy.router import (
    AuditLog, DataClass, DestinationClass, PrivacyContext, PrivacyRouter, enforce,
)


PAYLOAD = b"private repository evidence"
ENDPOINT = "https://api.example.invalid/v1/responses"


class FakeHumanVerifier:
    """Test-only authenticated human approval service, never production wiring."""

    def __init__(self, binding):
        self.binding = binding
        self.evidence = object()
        self.used = False

    def verify(self, evidence, binding):
        if evidence is not self.evidence or binding != self.binding or self.used:
            return False
        self.used = True
        return True


def binding(**overrides):
    fields = dict(
        operator_id="operator-1", project_id="project-1", payload=PAYLOAD,
        destination=ENDPOINT, purpose="answer repository question",
        expires_at=time.time() + 60,
    )
    fields.update(overrides)
    return ApprovalBinding.for_payload(**fields)


def build(tmp_path, *, approved=None, verifier=None):
    approved = approved or binding()
    verifier = verifier or FakeHumanVerifier(approved)
    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"), verifier=verifier,
    )
    receipt = authority.approve(approved, evidence=verifier.evidence)
    return authority, receipt, approved, verifier


def attempt(authority, receipt=None, **overrides):
    fields = dict(
        operator_id="operator-1", project_id="project-1", payload=PAYLOAD,
        destination=ENDPOINT, purpose="answer repository question",
        approval=receipt,
    )
    fields.update(overrides)
    return authority.authorize(**fields)


def test_default_deny_no_authenticated_authority(tmp_path, monkeypatch):
    for name in ("GVAI_CONSENT_TOKEN", "GVAI_STEX_REVIEW_TOKEN", "GVAI_USER_ID"):
        monkeypatch.setenv(name, "forged-operator-approval")
    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"),
    )
    with pytest.raises(PermissionError, match="authenticated_authority_missing"):
        authority.approve(binding(), evidence="forged-operator-approval")
    assert not attempt(authority).allowed


@pytest.mark.parametrize("evidence", [None, "consent-token", {"approved": True}])
def test_forged_human_approval_denied(tmp_path, evidence):
    scope = binding()
    verifier = FakeHumanVerifier(scope)
    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"), verifier=verifier,
    )
    with pytest.raises(PermissionError, match="human_approval_unverified"):
        authority.approve(scope, evidence=evidence)


def test_failed_authentication_is_closed_and_sanitized(tmp_path):
    class Unavailable:
        def verify(self, evidence, binding):
            raise RuntimeError("credential-sensitive-auth-error")

    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"), verifier=Unavailable(),
    )
    with pytest.raises(PermissionError, match="human_approval_unverified"):
        authority.approve(binding(), evidence=object())
    assert "credential-sensitive" not in (tmp_path / "authority.jsonl").read_text()


@pytest.mark.parametrize("result", [False, None, 1, "approved", {"approved": True}])
def test_truthy_verifier_result_is_not_approval(tmp_path, result):
    class Unverified:
        def verify(self, evidence, binding):
            return result

    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"), verifier=Unverified(),
    )
    with pytest.raises(PermissionError, match="human_approval_unverified"):
        authority.approve(binding(), evidence=object())


def test_human_verifier_must_approve_the_entire_requested_scope(tmp_path):
    scope = binding()
    verifier = FakeHumanVerifier(scope)
    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"), verifier=verifier,
    )
    with pytest.raises(PermissionError, match="human_approval_unverified"):
        authority.approve(
            replace(scope, project_id="unapproved-project"), evidence=verifier.evidence,
        )
    assert not verifier.used


def test_approval_and_receipt_replay_denied(tmp_path):
    authority, receipt, scope, verifier = build(tmp_path)
    with pytest.raises(PermissionError, match="human_approval_unverified"):
        authority.approve(scope, evidence=verifier.evidence)
    assert attempt(authority, receipt).allowed
    assert not attempt(authority, receipt).allowed


@pytest.mark.parametrize("changes", [
    {"payload": PAYLOAD + b"\n"},
    {"payload": PAYLOAD.decode()},
    {"operator_id": "worker-self-approved"},
    {"project_id": "other-project"},
    {"destination": "https://other.example.invalid/v1/responses"},
    {"purpose": "execute patch"},
])
def test_binding_substitution_burns_receipt(tmp_path, changes):
    authority, receipt, _, _ = build(tmp_path)
    decision = attempt(authority, receipt, **changes)
    assert not decision.allowed
    assert decision.reason == "approval_binding_mismatch"
    assert not attempt(authority, receipt).allowed


@pytest.mark.parametrize("receipt", [
    None, object(), "arbitrary-token", {"approved": True},
])
def test_worker_cannot_forge_receipt(tmp_path, receipt):
    authority, real_receipt, _, _ = build(tmp_path)
    assert not attempt(authority, receipt).allowed
    assert attempt(authority, real_receipt).allowed


def test_forged_receipt_cannot_execute_hash_or_equality_in_parent(tmp_path):
    class WorkerReceipt:
        def __hash__(self):
            raise AssertionError("untrusted hashing must not run")

        def __eq__(self, other):
            raise AssertionError("untrusted equality must not run")

    authority, receipt, _, _ = build(tmp_path)
    assert not attempt(authority, WorkerReceipt()).allowed
    assert attempt(authority, receipt).allowed


def test_receipt_serialization_does_not_transfer_parent_authority(tmp_path):
    import pickle

    authority, receipt, _, _ = build(tmp_path)
    assert not attempt(authority, pickle.loads(pickle.dumps(receipt))).allowed
    authority.shutdown()
    assert not attempt(authority, receipt).allowed


def test_worker_protocol_cannot_approve_or_override_parent_shutdown(tmp_path):
    import base64

    authority, receipt, _, _ = build(tmp_path / "parent")
    authority.shutdown()
    workspace = EncryptedProjectWorkspace(
        tmp_path / "storage",
        AESGCMControlPlane(
            bytes(range(32)),
            lambda request: request.worker_id == "worker-1",
        ),
        WorkspaceAuditLog(tmp_path / "workspace-audit.jsonl"),
    )
    broker = WorkspaceBroker(
        workspace, worker_id="worker-1", project_id="project-1",
        authority=WorkspaceAuthority(frozenset({"read", "write"})),
    )
    for operation in ("approve", "authorize_external_model", "reset_shutdown"):
        response = broker._WorkspaceBroker__handle_request(
            json.dumps({"operation": operation, "path": "approval.json"}).encode(),
        )
        assert response == {"ok": False, "error": "workspace request denied"}
    forged = json.dumps({"approved": True, "shutdown": False}).encode()
    response = broker._WorkspaceBroker__handle_request(
        json.dumps({
            "operation": "write", "path": "approval.json",
            "content_b64": base64.b64encode(forged).decode(),
        }).encode(),
    )
    assert response == {"ok": True}
    assert attempt(authority, receipt).reason == "external_shutdown"
    assert attempt(authority, forged).reason == "external_shutdown"


def test_receipt_cannot_cross_parent_authorities(tmp_path):
    authority, receipt, _, _ = build(tmp_path / "one")
    other, _, _, _ = build(tmp_path / "two")
    assert not attempt(other, receipt).allowed
    assert attempt(authority, receipt).allowed


def test_concurrent_replay_has_only_one_admission(tmp_path):
    authority, receipt, _, _ = build(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(pool.map(lambda _: attempt(authority, receipt), range(16)))
    assert sum(decision.allowed for decision in decisions) == 1


def test_expired_approval_denied(tmp_path):
    scope = binding(expires_at=time.time() - 1)
    verifier = FakeHumanVerifier(scope)
    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"), verifier=verifier,
    )
    with pytest.raises(PermissionError, match="approval_expired"):
        authority.approve(scope, evidence=verifier.evidence)
    assert not verifier.used


def test_expiry_and_wall_clock_rollback_do_not_extend_grant(tmp_path, monkeypatch):
    authority, receipt, scope, _ = build(tmp_path)
    monkeypatch.setattr(time, "time", lambda: scope.expires_at - 100)
    monotonic = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: monotonic + 120)
    assert attempt(authority, receipt).reason == "approval_expired"


def test_wall_clock_expiry_denies(tmp_path, monkeypatch):
    authority, receipt, scope, _ = build(tmp_path)
    monkeypatch.setattr(time, "time", lambda: scope.expires_at)
    assert attempt(authority, receipt).reason == "approval_expired"


@pytest.mark.parametrize("changes", [
    {"expires_at": float("nan")},
    {"expires_at": float("inf")},
    {"expires_at": "tomorrow"},
    {"destination": "http://api.example.invalid"},
    {"destination": "******example.invalid"},
    {"destination": ENDPOINT + "?credential=hidden"},
    {"project_id": ""},
    {"payload_sha256": "forged"},
])
def test_invalid_binding_denied(tmp_path, changes):
    scope = replace(binding(), **changes)
    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"),
    )
    with pytest.raises(PermissionError, match="invalid_approval_binding"):
        authority.approve(scope, evidence=object())


@pytest.mark.parametrize("control,reason", [
    ("revoke", "external_authority_revoked"),
    ("shutdown", "external_shutdown"),
])
def test_stop_overrides_grants_and_denies_new_approval(tmp_path, control, reason):
    authority, receipt, scope, verifier = build(tmp_path)
    getattr(authority, control)()
    assert attempt(authority, receipt).reason == reason
    assert attempt(authority, {"override_shutdown": True}).reason == reason
    with pytest.raises(PermissionError, match=reason):
        authority.approve(scope, evidence=verifier.evidence)


def test_shutdown_precedes_revocation(tmp_path):
    authority, receipt, _, _ = build(tmp_path)
    authority.revoke()
    authority.shutdown()
    assert attempt(authority, receipt).reason == "external_shutdown"


def test_shutdown_during_authentication_does_not_wait_or_mint_grant(tmp_path):
    started = threading.Event()
    finish = threading.Event()

    class WaitingVerifier:
        def verify(self, evidence, scope):
            started.set()
            assert finish.wait(5)
            return True

    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"), verifier=WaitingVerifier(),
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(authority.approve, binding(), evidence=object())
        try:
            assert started.wait(5)
            authority.shutdown()
        finally:
            finish.set()
        with pytest.raises(PermissionError, match="external_shutdown"):
            future.result(timeout=5)


def test_expiry_during_verification_does_not_mint_grant(tmp_path, monkeypatch):
    scope = binding()

    class SlowVerifier:
        def verify(self, evidence, binding):
            monkeypatch.setattr(time, "time", lambda: scope.expires_at)
            return True

    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"), verifier=SlowVerifier(),
    )
    with pytest.raises(PermissionError, match="approval_expired"):
        authority.approve(scope, evidence=object())


def test_issued_scope_is_snapshot_not_callers_mutable_object(tmp_path):
    authority, receipt, scope, _ = build(tmp_path)
    # Simulate hostile same-process mutation of the caller's copy; the grant
    # must retain the scope the verifier originally approved.
    object.__setattr__(scope, "project_id", "substituted")
    assert attempt(authority, receipt).allowed


def test_scope_mutation_during_verification_cannot_substitute_approval(tmp_path):
    scope = binding()

    class Verifier:
        def verify(self, evidence, verified_scope):
            assert verified_scope.project_id == "project-1"
            object.__setattr__(scope, "project_id", "substituted")
            return True

    authority = TrustedExternalModelAuthority(
        WorkspaceAuditLog(tmp_path / "authority.jsonl"), verifier=Verifier(),
    )
    receipt = authority.approve(scope, evidence=object())
    assert attempt(authority, receipt).allowed


def test_audit_is_sanitized_and_binds_exact_scope(tmp_path):
    scope = binding(
        operator_id="private-human", project_id="private-project",
        purpose="private-purpose",
    )
    authority, receipt, _, _ = build(tmp_path, approved=scope)
    assert attempt(
        authority, receipt, operator_id=scope.operator_id,
        project_id=scope.project_id, purpose=scope.purpose,
    ).allowed
    raw = (tmp_path / "authority.jsonl").read_text()
    for secret in ("private-human", "private-project", "private-purpose",
                   PAYLOAD.decode(), ENDPOINT):
        assert secret not in raw
    events = [json.loads(line) for line in raw.splitlines()]
    assert [event["operation"] for event in events] == ["approval", "external_model"]
    assert events[0]["resource_ref"] == events[1]["resource_ref"]
    assert all(event["allowed"] for event in events)


def test_audit_tampering_denies_and_irreversibly_revokes(tmp_path):
    authority, receipt, _, _ = build(tmp_path)
    audit = tmp_path / "authority.jsonl"
    audit.unlink()
    target = tmp_path / "target"
    target.write_text("untouched")
    audit.symlink_to(target)
    with pytest.raises(WorkspaceAuditError):
        attempt(authority, receipt)
    audit.unlink()
    audit.touch(mode=0o600)
    assert attempt(authority).reason == "external_authority_revoked"
    assert target.read_text() == "untouched"


def test_shutdown_remains_latched_when_audit_fails(tmp_path):
    authority, receipt, _, _ = build(tmp_path)
    audit = tmp_path / "authority.jsonl"
    audit.chmod(0o666)
    with pytest.raises(WorkspaceAuditError):
        authority.shutdown()
    audit.chmod(0o600)
    assert attempt(authority, receipt).reason == "external_shutdown"


def test_opt_in_router_denies_missing_authority_even_public_or_token(tmp_path):
    legacy = PrivacyRouter(AuditLog(tmp_path / "legacy.jsonl"))
    strict = PrivacyRouter(
        AuditLog(tmp_path / "strict.jsonl"), require_external_model_authority=True,
    )
    public = PrivacyContext("sensitive-user", "sensitive-project", DataClass.PUBLIC)
    assert legacy.authorize(public, DestinationClass.EXTERNAL_MODEL, "public").allowed
    assert not strict.authorize(public, DestinationClass.EXTERNAL_MODEL, "public").allowed
    shared = replace(
        public, data_class=DataClass.EXPLICITLY_SHARED, consent_token="forged",
    )
    with pytest.raises(PermissionError):
        enforce(strict, shared, DestinationClass.EXTERNAL_MODEL, PAYLOAD)
    raw = (tmp_path / "strict.jsonl").read_text()
    assert "sensitive" not in raw
    assert "forged" not in raw
    assert strict.authorize(public, DestinationClass.LOCAL).allowed
    assert strict.authorize(public, DestinationClass.WORLD_READ).allowed


def test_opt_in_parent_router_consumes_grant_and_obeys_shutdown(tmp_path):
    authority, receipt, _, _ = build(tmp_path)
    router = PrivacyRouter(
        AuditLog(tmp_path / "unused-legacy.jsonl"),
        external_model_authority=authority,
    )
    context = PrivacyContext("operator-1", "project-1", DataClass.PUBLIC)
    assert not router.decide(context, DestinationClass.EXTERNAL_MODEL).allowed
    assert enforce(
        router, context, DestinationClass.EXTERNAL_MODEL, PAYLOAD,
        approval=receipt, model_destination=ENDPOINT,
        purpose="answer repository question",
    ).allowed
    authority.shutdown()
    with pytest.raises(PermissionError, match="external_shutdown"):
        enforce(
            router, context, DestinationClass.EXTERNAL_MODEL, PAYLOAD,
            approval=receipt, model_destination=ENDPOINT,
            purpose="answer repository question",
        )
    assert not (tmp_path / "unused-legacy.jsonl").exists()
