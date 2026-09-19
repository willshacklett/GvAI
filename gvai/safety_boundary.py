"""Narrow boundary for future GVAI Safety Systems governance decisions.

This module deliberately contains no Safety Systems implementation. A future
adapter can provide the decider callable without changing worker-facing code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


GovernanceStatus = str
_VALID_STATUSES = {"allow", "deny", "warn", "unavailable"}


@dataclass(frozen=True)
class GovernanceDecision:
    status: GovernanceStatus
    reason: str
    configured: bool

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUSES:
            raise ValueError("Unsupported governance status.")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "configured": self.configured,
        }


GovernanceDecider = Callable[[str, Mapping[str, object]], GovernanceDecision]


class SafetySystemsBoundary:
    """Call an external governance service only when one is configured."""

    def __init__(self, decider: GovernanceDecider | None = None) -> None:
        self._decider = decider

    @property
    def configured(self) -> bool:
        return self._decider is not None

    def decide(
        self,
        action: str,
        *,
        context: Mapping[str, object] | None = None,
    ) -> GovernanceDecision:
        if self._decider is None:
            return GovernanceDecision(
                status="unavailable",
                reason="GVAI Safety Systems governance is not configured.",
                configured=False,
            )
        decision = self._decider(action, context or {})
        if not isinstance(decision, GovernanceDecision):
            raise TypeError("The Safety Systems decider must return GovernanceDecision.")
        return decision


DEFAULT_SAFETY_SYSTEMS_BOUNDARY = SafetySystemsBoundary()