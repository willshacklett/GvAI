from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Dict

TIMELINE_PATH = Path("data/gv_phase_timeline.json")


def empty_timeline() -> Dict[str, Any]:
    return {
        "events": [],
        "current_phase": "UNKNOWN",
        "previous_phase": "UNKNOWN",
        "transition_count": 0,
        "phase_counts": {},
        "time_in_current_phase": 0,
        "return_to_elastic_count": 0,
    }


def load_timeline() -> Dict[str, Any]:
    if not TIMELINE_PATH.exists():
        return empty_timeline()

    try:
        return json.loads(TIMELINE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return empty_timeline()


def save_timeline(state: Dict[str, Any]) -> None:
    TIMELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TIMELINE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def reset_timeline() -> Dict[str, Any]:
    state = empty_timeline()
    save_timeline(state)
    return state


def update_timeline(heartbeat: Dict[str, Any]) -> Dict[str, Any]:
    state = load_timeline()

    phase = heartbeat.get("phase", "UNKNOWN")
    previous = state.get("current_phase", "UNKNOWN")

    events = state.get("events", [])
    event = {
        "phase": phase,
        "previous_phase": previous,
        "gv": heartbeat.get("gv"),
        "debt": heartbeat.get("debt"),
        "elasticity": heartbeat.get("elasticity"),
        "masking_distance": heartbeat.get("masking_distance"),
        "timestamp": heartbeat.get("timestamp"),
        "recoverability_state": heartbeat.get("recoverability_state"),
    }

    events.append(event)
    events = events[-100:]

    transition_count = int(state.get("transition_count", 0))
    return_to_elastic_count = int(state.get("return_to_elastic_count", 0))

    if previous != "UNKNOWN" and phase != previous:
        transition_count += 1

        if phase == "ELASTIC":
            return_to_elastic_count += 1

    if phase == previous:
        time_in_current_phase = int(state.get("time_in_current_phase", 0)) + 1
    else:
        time_in_current_phase = 1

    phase_counts = state.get("phase_counts", {})
    phase_counts[phase] = int(phase_counts.get(phase, 0)) + 1

    next_state = {
        "events": events,
        "current_phase": phase,
        "previous_phase": previous,
        "transition_count": transition_count,
        "phase_counts": phase_counts,
        "time_in_current_phase": time_in_current_phase,
        "return_to_elastic_count": return_to_elastic_count,
    }

    save_timeline(next_state)
    return next_state
