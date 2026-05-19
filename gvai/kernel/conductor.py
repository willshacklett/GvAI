from __future__ import annotations

from typing import Any, Dict

from gvai.kernel.orchestra import orchestra_confidence
from gvai.kernel.elevation import elevation_gate


def conductor_decision(
    musicians: list[Dict[str, Any]],
    vitals: Dict[str, Any] | None = None,
    belief: Dict[str, Any] | None = None,
    required_note: float = 0.85,
    timing_tolerance: float = 0.08,
) -> Dict[str, Any]:

    vitals = vitals or {}
    belief = belief or {}

    orchestra = orchestra_confidence(musicians)
    elevation = elevation_gate(
        musicians=musicians,
        required_note=required_note,
        timing_tolerance=timing_tolerance,
    )

    life_state = vitals.get("life_state", "UNKNOWN")
    belief_mode = belief.get("belief_mode", "UNKNOWN")

    go_time = bool(elevation.get("go_time", False))
    orchestra_state = orchestra.get("state")

    if go_time and orchestra_state == "FULL_HARMONY":
        conductor_state = "PERFORM"
        crowd_state = "RESONANCE_READY"
        action = "open_the_show"
        meaning = "The orchestra is synchronized, recoverable, and ready to elevate the room."

    elif go_time:
        conductor_state = "GO_TIME"
        crowd_state = "ATTENTION_LOCKING"
        action = "begin_with_controlled_expansion"
        meaning = "The orchestra hit the note, but conductor should keep monitoring stability."

    elif orchestra_state in {"BUILDING_CONFIDENCE", "FRAGILE_COORDINATION"}:
        conductor_state = "REHEARSE"
        crowd_state = "NOT_READY"
        action = "tighten_sections_before_expansion"
        meaning = "The orchestra is improving but not ready to carry the audience yet."

    else:
        conductor_state = "RECOVER"
        crowd_state = "DISSONANCE_RISK"
        action = "restore_tune_before_performance"
        meaning = "Recoverability must be restored before performance."

    if life_state in {"CRITICAL", "UNSTABLE"}:
        conductor_state = "RECOVER"
        crowd_state = "DO_NOT_EXPAND"
        action = "stabilize_vitals_first"
        meaning = "Vital signs override performance readiness."

    if belief_mode == "BELIEF_COLLAPSE_RISK":
        conductor_state = "RECOVER"
        crowd_state = "DO_NOT_EXPAND"
        action = "restore_belief_before_show"
        meaning = "Belief collapse risk prevents expansion."

    return {
        "conductor_state": conductor_state,
        "crowd_state": crowd_state,
        "recommended_action": action,
        "meaning": meaning,
        "orchestra": orchestra,
        "elevation": elevation,
        "vitals": vitals,
        "belief": belief,
    }
