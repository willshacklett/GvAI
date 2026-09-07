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

    def __init__(self, audit_log=None):
        self.audit_log = audit_log or AuditLog()

    def decide(self, context, destination):

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

    def authorize(self, context, destination, payload=""):

        decision = self.decide(context, destination)

        self.audit_log.write(
            context,
            decision,
            payload
        )

        return decision


def enforce(router, context, destination, payload=""):
    """
    Hard enforcement helper.

    External providers should call this BEFORE transmitting data.
    """

    decision = router.authorize(
        context,
        destination,
        payload
    )

    if not decision.allowed:
        raise PermissionError(
            f"GVAI blocked outbound request: {decision.reason}"
        )

    return decision
