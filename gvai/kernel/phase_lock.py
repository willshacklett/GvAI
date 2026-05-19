from __future__ import annotations

from typing import Any, Dict


def detect_phase_lock(timeline: Dict[str, Any]) -> Dict[str, Any]:
    phase = timeline.get("current_phase", "UNKNOWN")
    time_in_phase = int(timeline.get("time_in_current_phase", 0) or 0)
    return_to_elastic = int(timeline.get("return_to_elastic_count", 0) or 0)
    transition_count = int(timeline.get("transition_count", 0) or 0)

    locked = False
    severity = "NONE"
    reason = "No phase lock detected."

    if phase in {"DEGRADING", "CASCADE_RISK", "COLLAPSE_ZONE"} and time_in_phase >= 3:
        locked = True
        severity = "HIGH"
        reason = "System is persisting in a high-risk phase."

    elif phase == "TURBULENT" and time_in_phase >= 5:
        locked = True
        severity = "MEDIUM"
        reason = "System is stuck in turbulence without returning to elastic state."

    elif transition_count >= 5 and return_to_elastic == 0:
        locked = True
        severity = "MEDIUM"
        reason = "Repeated transitions without return to ELASTIC."

    return {
        "phase": phase,
        "time_in_current_phase": time_in_phase,
        "transition_count": transition_count,
        "return_to_elastic_count": return_to_elastic,
        "phase_locked": locked,
        "severity": severity,
        "reason": reason,
    }
