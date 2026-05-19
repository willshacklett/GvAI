from __future__ import annotations

from typing import Any, Dict, List


def elevation_gate(
    musicians: List[Dict[str, Any]],
    required_note: float = 0.85,
    timing_tolerance: float = 0.08,
) -> Dict[str, Any]:

    if not musicians:
        return {
            "state": "NO_ORCHESTRA",
            "go_time": False,
            "reason": "No musicians available to test.",
            "conductor_action": "assemble_orchestra",
        }

    ready = []
    late = []
    flat = []

    for musician in musicians:
        name = musician.get("name", "unknown")

        note = float(musician.get("note", 0.0) or 0.0)
        timing_error = abs(float(musician.get("timing_error", 1.0) or 0.0))
        confidence = float(musician.get("confidence", 0.0) or 0.0)
        recoverability = float(musician.get("recoverability", 0.0) or 0.0)

        hits_note = note >= required_note
        on_time = timing_error <= timing_tolerance
        can_recover = recoverability >= 0.70
        believes = confidence >= 0.70

        if hits_note and on_time and can_recover and believes:
            ready.append(name)
        else:
            if not hits_note:
                flat.append(name)
            if not on_time:
                late.append(name)

    count = len(musicians)
    readiness = round(len(ready) / count, 3)

    go_time = readiness == 1.0

    if go_time:
        state = "GO_TIME"
        action = "expand_and_perform"
        reason = "Every musician hit the note on time with recoverability intact."
    elif readiness >= 0.75:
        state = "ALMOST_READY"
        action = "tighten_timing_then_retry"
        reason = "Most musicians elevated, but the orchestra is not fully synchronized."
    elif readiness >= 0.50:
        state = "BUILDING_ELEVATION"
        action = "rehearse_weak_sections"
        reason = "Some sections are rising, but coherence is not ready for full performance."
    else:
        state = "NOT_READY"
        action = "restore_baseline_before_expansion"
        reason = "The orchestra cannot elevate together yet."

    return {
        "state": state,
        "go_time": go_time,
        "readiness": readiness,
        "ready_members": ready,
        "flat_members": flat,
        "late_members": late,
        "required_note": required_note,
        "timing_tolerance": timing_tolerance,
        "conductor_action": action,
        "reason": reason,
        "meaning": "Elevation requires confidence, timing, recoverability, and shared arrival on the note.",
    }
