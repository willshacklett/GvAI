from __future__ import annotations

from typing import Any, Dict


def compute_vitals(
    heartbeat: Dict[str, Any],
    timeline: Dict[str, Any],
    phase_lock: Dict[str, Any],
    recovery_pride: Dict[str, Any],
) -> Dict[str, Any]:

    gv = float(heartbeat.get("gv", 0.0) or 0.0)
    elasticity = float(heartbeat.get("elasticity", 1.0) or 1.0)
    debt = float(heartbeat.get("debt", 0.0) or 0.0)
    masking = float(heartbeat.get("masking_distance", 0.0) or 0.0)

    phase = heartbeat.get("phase", "UNKNOWN")
    recoverability_state = heartbeat.get("recoverability_state", "UNKNOWN")

    time_in_phase = int(timeline.get("time_in_current_phase", 0) or 0)
    transitions = int(timeline.get("transition_count", 0) or 0)

    locked = bool(phase_lock.get("phase_locked", False))
    pride = float(recovery_pride.get("recovery_pride", 0.0) or 0.0)

    pulse = round(gv, 3)
    breath = round(elasticity, 3)
    strain = round(min(1.0, debt / 6.0), 3)
    hidden_stress = round(masking, 3)

    if locked or phase in {"CASCADE_RISK", "COLLAPSE_ZONE"}:
        life_state = "CRITICAL"
    elif phase == "DEGRADING" or pride < 0.35:
        life_state = "UNSTABLE"
    elif phase == "TURBULENT" or hidden_stress > 0.10:
        life_state = "STRESSED"
    else:
        life_state = "ALIVE_STABLE"

    return {
        "life_state": life_state,
        "pulse": pulse,
        "breath": breath,
        "strain": strain,
        "hidden_stress": hidden_stress,
        "phase": phase,
        "recoverability_state": recoverability_state,
        "phase_locked": locked,
        "recovery_pride": pride,
        "time_in_current_phase": time_in_phase,
        "transition_count": transitions,
        "meaning": "GV vital signs measure whether the system remains recoverable under stress.",
    }
