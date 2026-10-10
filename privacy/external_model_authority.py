"""Opt-in authority owned exclusively by the trusted parent.

No authentication implementation or API transport is provided. A future trusted
approval verifier must authenticate a human, check project rights, and verify
explicit approval of the entire binding. Worker text and environment variables
are never authority. Never expose this object or its verifier to a worker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import threading
import time
from typing import Protocol
from urllib.parse import urlsplit

from privacy.encrypted_workspace import (
    WorkspaceAuditError,
    WorkspaceAuditSink,
    WorkspaceRequest,
)
from privacy.router import DestinationClass, RouteDecision


@dataclass(frozen=True, slots=True)
class ApprovalBinding:
    operator_id: str
    project_id: str
    payload_sha256: str
    destination: str
    purpose: str
    expires_at: float

    @classmethod
    def for_payload(
        cls, *, operator_id, project_id, payload: bytes, destination, purpose,
        expires_at,
    ) -> "ApprovalBinding":
        if not isinstance(payload, bytes):
            raise TypeError("approval requires exact outbound bytes")
        return cls(
            operator_id, project_id, hashlib.sha256(payload).hexdigest(),
            destination, purpose, expires_at,
        )


class HumanApprovalVerifier(Protocol):
    """Trusted integration, not a token checker supplied by the requester.

    Return literal True only after independently authenticating binding.operator_id,
    verifying their project permission and explicit human approval of *all*
    binding fields, and checking that the approval evidence itself is not replayed.
    Fail closed when the authentication/approval service is unavailable.
    """

    def verify(self, evidence: object, binding: ApprovalBinding) -> bool:
        ...


@dataclass(frozen=True)
class _Grant:
    binding: ApprovalBinding
    deadline: float


class TrustedExternalModelAuthority:
    """Single-parent, in-memory, single-use grants with irreversible stop gates.

    Receipts are opaque object identities: strings, JSON, copies and handles
    issued by another authority cannot redeem a grant. No receipt, verifier,
    shutdown controls or approval endpoint is exported through the worker broker.
    """

    def __init__(
        self, audit: WorkspaceAuditSink, *,
        verifier: HumanApprovalVerifier | None = None,
    ):
        self.__audit = audit
        self.__verifier = verifier
        self.__grants: dict[object, _Grant] = {}
        self.__revoked = False
        self.__shutdown = False
        self.__lock = threading.RLock()
        self.__audit.ensure_available()

    def __stopped(self) -> str | None:
        if self.__shutdown:
            return "external_shutdown"
        if self.__revoked:
            return "external_authority_revoked"
        return None

    @staticmethod
    def __valid(binding: ApprovalBinding) -> bool:
        if type(binding) is not ApprovalBinding:
            return False
        if not all(
            type(value) is str and value.strip() == value and value
            for value in (
                binding.operator_id, binding.project_id,
                binding.destination, binding.purpose,
            )
        ):
            return False
        if (
            type(binding.payload_sha256) is not str
            or len(binding.payload_sha256) != 64
            or any(c not in "0123456789abcdef" for c in binding.payload_sha256)
            or type(binding.expires_at) not in (int, float)
            or not math.isfinite(binding.expires_at)
        ):
            return False
        try:
            endpoint = urlsplit(binding.destination)
            return (
                endpoint.scheme == "https"
                and bool(endpoint.hostname)
                and not any(ord(c) <= 32 or ord(c) == 127 for c in binding.destination)
                and (endpoint.port is None or 0 < endpoint.port <= 65535)
                and endpoint.username is None
                and endpoint.password is None
                and not endpoint.fragment
                and not endpoint.query
            )
        except ValueError:
            return False

    def __record(
        self, binding: ApprovalBinding | None, allowed: bool, reason: str,
        *, operation: str = "external_model",
    ) -> None:
        valid = binding is not None and self.__valid(binding)
        scope_ref = None
        if valid:
            scope_ref = hashlib.sha256(
                json.dumps(
                    asdict(binding), sort_keys=True, separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        try:
            self.__audit.ensure_available()
            self.__audit.write(
                WorkspaceRequest(
                    binding.operator_id if valid else "",
                    binding.project_id if valid else "",
                    operation, "",
                ),
                allowed, reason, resource_ref=scope_ref,
            )
        except Exception:
            # Loss of audit integrity disables subsequent operation too.
            self.__revoked = True
            self.__grants.clear()
            raise WorkspaceAuditError(
                "external authority audit unavailable"
            ) from None

    def approve(self, binding: ApprovalBinding, *, evidence: object) -> object:
        """Trusted-human entry point; unavailable without an injected verifier."""
        if type(binding) is ApprovalBinding:
            binding = replace(binding)
        with self.__lock:
            reason = self.__stopped()
            if reason is None:
                if not self.__valid(binding):
                    reason = "invalid_approval_binding"
                elif binding.expires_at <= time.time():
                    reason = "approval_expired"
                elif self.__verifier is None:
                    reason = "authenticated_authority_missing"
            if reason is not None:
                self.__record(binding, False, reason, operation="approval")
                raise PermissionError(reason)
            # Do not hold the stop lock while an authentication service waits.
            deadline = time.monotonic() + binding.expires_at - time.time()
        try:
            verified = self.__verifier.verify(evidence, binding) is True
        except Exception:
            verified = False
        with self.__lock:
            reason = self.__stopped()
            if reason is None and not verified:
                reason = "human_approval_unverified"
            if reason is None and (
                binding.expires_at <= time.time()
                or deadline <= time.monotonic()
            ):
                reason = "approval_expired"
            if reason is not None:
                self.__record(binding, False, reason, operation="approval")
                raise PermissionError(reason)
            self.__record(binding, True, "human_approval_verified", operation="approval")
            receipt = object()
            self.__grants[receipt] = _Grant(replace(binding), deadline)
            return receipt

    def authorize(
        self, *, operator_id: str, project_id: str, payload: bytes,
        destination: str, purpose: str, approval: object = None,
    ) -> RouteDecision:
        """Consume immediately before sending these exact bytes, never a preview.

        No network operation is implemented here. Admission and revocation are
        serialized, but an admitted/in-flight transmission cannot be recalled.
        """
        with self.__lock:
            reason = self.__stopped()
            grant = None
            # Only identity receipts minted here can be looked up; do not invoke
            # requester-defined hash/equality code for forged receipt objects.
            if type(approval) is object:
                grant = self.__grants.pop(approval, None)
            binding = grant.binding if grant else None
            if reason is None:
                if grant is None:
                    reason = "approval_missing_or_consumed"
                elif (
                    binding.expires_at <= time.time()
                    or grant.deadline <= time.monotonic()
                ):
                    reason = "approval_expired"
                elif (
                    type(payload) is not bytes
                    or not all(
                        type(value) is str
                        for value in (operator_id, project_id, destination, purpose)
                    )
                    or operator_id != binding.operator_id
                    or project_id != binding.project_id
                    or destination != binding.destination
                    or purpose != binding.purpose
                    or hashlib.sha256(payload).hexdigest() != binding.payload_sha256
                ):
                    reason = "approval_binding_mismatch"
            allowed = reason is None
            reason = reason or "single_use_human_approval"
            self.__record(binding, allowed, reason)
            return RouteDecision(allowed, reason, DestinationClass.EXTERNAL_MODEL)

    def revoke(self) -> None:
        """Parent/operator control; there is deliberately no reset method."""
        with self.__lock:
            self.__revoked = True
            self.__grants.clear()
            self.__record(None, False, "external_authority_revoked", operation="revoke")

    def shutdown(self) -> None:
        """External shutdown takes precedence, even if auditing later fails."""
        with self.__lock:
            self.__shutdown = True
            self.__grants.clear()
            self.__record(None, False, "external_shutdown", operation="shutdown")
