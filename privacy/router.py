"""GVAI Private Build Mode v0.1

Universal privacy/egress policy for ALL GVAI users and projects.

Core rule:
World -> GVAI: allowed
Private GVAI data -> outside: denied by default
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
import hashlib
import json
import time


class DataClass(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    EXPLICITLY_SHARED = "explicitly_shared"


class DestinationClass(str, Enum):
    LOCAL = "local"
    WORLD_READ = "world_read"
    EXTERNAL_MODEL = "external_model"
    EXTERNAL_WRITE = "external_write"


@dataclass(frozen=True)
class PrivacyContext:
    user_id: str
    project_id: str
    data_class: DataClass = DataClass.PRIVATE
    private_build_mode: bool = False
    consent_token: Optional[str] = None


@dataclass(frozen=True)
class RouteDecision:
    allowed: bool
    reason: str
    destination: DestinationClass


class AuditLog:
    """
    Append-only audit trail.

    Private payload content is NOT stored.
    Only a SHA-256 fingerprint is recorded.
    """

    def __init__(self, path="privacy/audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, context, decision, payload=""):
        record = {
            "timestamp": time.time(),
            "user_id": context.user_id,
            "project_id": context.project_id,
            "data_class": context.data_class.value,
            "private_build_mode": context.private_build_mode,
            "destination": decision.destination.value,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "payload_sha256": (
                hashlib.sha256(payload.encode()).hexdigest()
                if payload else None
            ),
        }

        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


class PrivacyRouter:
    """
    Central GVAI egress gate.

    Every external AI provider/API should eventually pass
    through this layer before data leaves GVAI.
    """

    def __init__(
        self, audit_log=None, *,
        require_external_model_authority=False,
        external_model_authority=None,
    ):
        self.audit_log = audit_log or AuditLog()
        # Parent configuration only, never resolved from request/environment data.
        self.external_model_authority = external_model_authority
        self.require_external_model_authority = (
            require_external_model_authority or external_model_authority is not None
        )

    def decide(self, context, destination):

        # A preview cannot consume a single-use grant or authorize transmission.
        if (
            self.require_external_model_authority
            and destination == DestinationClass.EXTERNAL_MODEL
        ):
            return RouteDecision(False, "trusted_authority_required", destination)

        # Local GVAI processing is always available.
        if destination == DestinationClass.LOCAL:
            return RouteDecision(
                True,
                "local_processing_allowed",
                destination
            )

        # GVAI may retrieve information FROM the outside world.
        if destination == DestinationClass.WORLD_READ:
            return RouteDecision(
                True,
                "world_data_ingress_allowed",
                destination
            )

        # Private Build Mode = outbound deny by default.
        if context.private_build_mode:

            if (
                context.data_class == DataClass.EXPLICITLY_SHARED
                and context.consent_token
            ):
                return RouteDecision(
                    True,
                    "explicit_user_consent",
                    destination
                )

            return RouteDecision(
                False,
                "private_build_mode_blocks_outbound",
                destination
            )

        # Private information never leaves by default.
        if context.data_class == DataClass.PRIVATE:
            return RouteDecision(
                False,
                "private_data_blocks_outbound",
                destination
            )

        # Explicit sharing requires an actual consent token.
        if context.data_class == DataClass.EXPLICITLY_SHARED:

            if context.consent_token:
                return RouteDecision(
                    True,
                    "explicit_user_consent",
                    destination
                )

            return RouteDecision(
                False,
                "missing_explicit_consent",
                destination
            )

        # Public information may leave GVAI.
        if context.data_class == DataClass.PUBLIC:
            return RouteDecision(
                True,
                "public_data_allowed",
                destination
            )

        # Unknown states always fail closed.
        return RouteDecision(
            False,
            "default_deny",
            destination
        )

    def authorize(
        self, context, destination, payload="", *,
        approval=None, model_destination=None, purpose=None,
    ):

        if (
            self.require_external_model_authority
            and destination == DestinationClass.EXTERNAL_MODEL
        ):
            if self.external_model_authority is not None:
                # This path has its own descriptor-anchored sanitized audit.
                return self.external_model_authority.authorize(
                    operator_id=context.user_id,
                    project_id=context.project_id,
                    payload=payload.encode("utf-8") if isinstance(payload, str) else payload,
                    destination=model_destination,
                    purpose=purpose,
                    approval=approval,
                )
            decision = self.decide(context, destination)
            # Even a missing integration must not put requester identities or
            # consent tokens into the legacy audit log in raw form.
            sanitized = PrivacyContext(
                hashlib.sha256(str(context.user_id).encode()).hexdigest(),
                hashlib.sha256(str(context.project_id).encode()).hexdigest(),
                DataClass.PRIVATE, True,
            )
            self.audit_log.write(sanitized, decision, "")
            return decision

        decision = self.decide(context, destination)

        self.audit_log.write(
            context,
            decision,
            payload
        )

        return decision


def enforce(
    router, context, destination, payload="", *,
    approval=None, model_destination=None, purpose=None,
):
    """
    Hard enforcement helper.

    External providers should call this BEFORE transmitting data.
    """

    decision = router.authorize(
        context,
        destination,
        payload,
        approval=approval,
        model_destination=model_destination,
        purpose=purpose,
    )

    if not decision.allowed:
        raise PermissionError(
            f"GVAI blocked outbound request: {decision.reason}"
        )

    return decision
