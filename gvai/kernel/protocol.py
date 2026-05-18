from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def recoverability_state_from_phase(phase: str) -> str:
    return {
        "ELASTIC": "RECOVERABLE",
        "TURBULENT": "STRESSED",
        "DEGRADING": "DEGRADING",
        "CASCADE_RISK": "CASCADE_RISK",
        "COLLAPSE_ZONE": "NON_RECOVERABLE_RISK",
    }.get(phase, "STRESSED")


def compute_masking_distance(
    visible_coherence: float | None,
    recoverability_score: float | None,
) -> float:
    if visible_coherence is None or recoverability_score is None:
        return 0.0

    return round(
        abs(clamp(visible_coherence) - clamp(recoverability_score)),
        3,
    )


def build_gv_heartbeat(
    runtime: Dict[str, Any] | None = None,
    debt: Dict[str, Any] | None = None,
    phase: Dict[str, Any] | None = None,
    visible_coherence: float | None = None,
    context: str = "gv-runtime-protocol",
) -> Dict[str, Any]:

    runtime = runtime or {}
    debt = debt or {}
    phase = phase or {}

    gv = float(runtime.get("gv", 0.0) or 0.0)

    debt_value = float(debt.get("debt", 0.0) or 0.0)

    recoverability_score = 1.0 - (debt_value / 10.0)

    phase_name = phase.get("phase", "ELASTIC")

    payload = {
        "protocol": "GV_RUNTIME_PROTOCOL",
        "version": "0.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "context": context,

        "gv": round(gv, 3),

        "phase": phase_name,

        "recoverability_state":
            recoverability_state_from_phase(phase_name),

        "debt": debt_value,

        "elasticity":
            float(debt.get("elasticity", 1.0) or 1.0),

        "debt_velocity":
            float(debt.get("debt_velocity", 0.0) or 0.0),

        "masking_distance":
            compute_masking_distance(
                visible_coherence,
                recoverability_score,
            ),

        "visible_coherence": visible_coherence,
    }

    return payload


def validate_heartbeat(payload: Dict[str, Any]) -> Dict[str, Any]:

    required = [
        "protocol",
        "version",
        "timestamp",
        "gv",
        "phase",
        "recoverability_state",
        "debt",
        "elasticity",
        "debt_velocity",
        "masking_distance",
    ]

    missing = [
        field for field in required
        if field not in payload
    ]

    return {
        "valid": not missing,
        "missing": missing,
    }
