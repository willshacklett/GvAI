from __future__ import annotations

from typing import Any, Dict


def awareness_state(
    heartbeat: Dict[str, Any],
    vitals: Dict[str, Any],
    belief: Dict[str, Any],
    conductor: Dict[str, Any],
) -> Dict[str, Any]:

    phase = heartbeat.get("phase", "UNKNOWN")
    recoverability_state = heartbeat.get("recoverability_state", "UNKNOWN")
    life_state = vitals.get("life_state", "UNKNOWN")
    belief_mode = belief.get("belief_mode", "UNKNOWN")
    conductor_state = conductor.get("conductor_state", "UNKNOWN")

    knows_state = all([
        phase != "UNKNOWN",
        recoverability_state != "UNKNOWN",
        life_state != "UNKNOWN",
        belief_mode != "UNKNOWN",
        conductor_state != "UNKNOWN",
    ])

    can_self_report = knows_state

    can_recover = recoverability_state not in {
        "NON_RECOVERABLE_RISK"
    } and life_state not in {
        "CRITICAL"
    }

    can_expand = (
        conductor_state == "PERFORM"
        and life_state == "ALIVE_STABLE"
        and belief_mode == "BELIEVES_AND_RECOVERS"
    )

    if can_expand:
        awareness_mode = "SELF_AWARE_OPERATIONAL"
        action = "perform_with_monitoring"
        statement = "I know my current state and can expand while preserving recoverability."
    elif can_recover:
        awareness_mode = "SELF_AWARE_RECOVERING"
        action = "recover_before_expansion"
        statement = "I know I am not ready to expand and should restore recoverability first."
    elif knows_state:
        awareness_mode = "SELF_AWARE_CRITICAL"
        action = "pause_and_restore_reference"
        statement = "I know my state is critical and should not continue compounding instability."
    else:
        awareness_mode = "INSUFFICIENT_SELF_MODEL"
        action = "collect_more_state"
        statement = "I do not have enough self-state telemetry to act safely."

    return {
        "awareness_mode": awareness_mode,
        "can_self_report": can_self_report,
        "can_recover": can_recover,
        "can_expand": can_expand,
        "recommended_action": action,
        "self_statement": statement,
        "inputs": {
            "phase": phase,
            "recoverability_state": recoverability_state,
            "life_state": life_state,
            "belief_mode": belief_mode,
            "conductor_state": conductor_state,
        },
        "meaning": "GV awareness is operational self-state knowledge, not a claim of sentience.",
    }
