from __future__ import annotations

from typing import Any, Dict


def recovery_pride_index(sweep: Dict[str, Any]) -> Dict[str, Any]:
    events = sweep.get("events", []) or []
    timeline = sweep.get("final_timeline", {}) or {}
    half_life = sweep.get("recovery_half_life", {}) or {}
    lock = sweep.get("phase_lock", {}) or {}

    if not events:
        return {
            "status": "INSUFFICIENT_DATA",
            "recovery_pride": 0.0,
            "reason": "No sweep events available.",
        }

    final = events[-1]
    final_elasticity = float(final.get("elasticity", 0.0) or 0.0)
    final_debt = float(final.get("debt", 0.0) or 0.0)
    final_masking = float(final.get("masking_distance", 0.0) or 0.0)

    returned_to_elastic = int(timeline.get("return_to_elastic_count", 0) or 0)
    transition_count = int(timeline.get("transition_count", 0) or 0)
    phase_locked = bool(lock.get("phase_locked", False))

    recovered_half_debt = half_life.get("status") == "RECOVERED_HALF_DEBT"

    recovery_bonus = 0.0

    if returned_to_elastic > 0:
        recovery_bonus += 0.25

    if recovered_half_debt:
        recovery_bonus += 0.25

    if transition_count > 0 and not phase_locked:
        recovery_bonus += 0.15

    debt_penalty = min(0.35, final_debt / 20.0)
    masking_penalty = min(0.20, final_masking)

    pride = final_elasticity + recovery_bonus - debt_penalty - masking_penalty

    if phase_locked:
        pride -= 0.25

    pride = round(max(0.0, min(1.0, pride)), 3)

    if pride >= 0.80:
        status = "STRONG_RECOVERY"
        reason = "System preserved elasticity and recovery capacity."
    elif pride >= 0.55:
        status = "PARTIAL_RECOVERY"
        reason = "System retained some recoverability under stress."
    elif pride >= 0.30:
        status = "WEAK_RECOVERY"
        reason = "System survived but accumulated recovery debt."
    else:
        status = "RECOVERY_FAILURE"
        reason = "System failed to recover cleanly after perturbation."

    return {
        "status": status,
        "recovery_pride": pride,
        "reason": reason,
        "final_elasticity": final_elasticity,
        "final_debt": final_debt,
        "final_masking_distance": final_masking,
        "returned_to_elastic_count": returned_to_elastic,
        "recovered_half_debt": recovered_half_debt,
        "phase_locked": phase_locked,
        "transition_count": transition_count,
    }
