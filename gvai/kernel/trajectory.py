from __future__ import annotations

from pathlib import Path
import json
from statistics import mean
from typing import Any, Dict

STATE_PATH = Path("data/gv_kernel_trajectory.json")


def empty_state() -> Dict[str, Any]:
    return {
        "events": [],
        "rolling_gv": None,
        "drift_trend": 0.0,
        "recoverability_trend": 0.0,
        "trajectory_mode": "UNKNOWN",
        "total_events": 0,
    }


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return empty_state()
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return empty_state()


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def reset_state() -> Dict[str, Any]:
    state = empty_state()
    save_state(state)
    return state


def update_state(runtime_payload: Dict[str, Any], label: str = "kernel") -> Dict[str, Any]:
    state = load_state()

    risks = runtime_payload.get("gv_risks") or {}

    event = {
        "label": label,
        "gv": float(runtime_payload.get("gv", 0.0)),
        "mode": runtime_payload.get("gv_mode"),
        "action": runtime_payload.get("gv_action"),
        "risks": risks,
        "judgment": runtime_payload.get("gv_judgment", ""),
    }

    events = state.get("events", [])
    events.append(event)
    events = events[-25:]

    gv_values = [float(e.get("gv", 0.0)) for e in events]
    drift_values = [float(e.get("risks", {}).get("drift", 0.0)) for e in events]
    recovery_values = [float(e.get("risks", {}).get("recoverability", 0.0)) for e in events]

    recent_gv = gv_values[-5:]
    rolling_gv = round(mean(recent_gv), 3) if recent_gv else None

    drift_trend = 0.0
    recoverability_trend = 0.0

    if len(drift_values) >= 10:
        drift_trend = round(mean(drift_values[-5:]) - mean(drift_values[-10:-5]), 3)

    if len(recovery_values) >= 10:
        recoverability_trend = round(mean(recovery_values[-5:]) - mean(recovery_values[-10:-5]), 3)

    if rolling_gv is None:
        trajectory_mode = "UNKNOWN"
    elif rolling_gv >= 0.75 and drift_trend <= 0.05 and recoverability_trend <= 0.05:
        trajectory_mode = "STABLE"
    elif rolling_gv >= 0.55:
        trajectory_mode = "WATCH"
    else:
        trajectory_mode = "DEGRADING"

    next_state = {
        "events": events,
        "rolling_gv": rolling_gv,
        "drift_trend": drift_trend,
        "recoverability_trend": recoverability_trend,
        "trajectory_mode": trajectory_mode,
        "total_events": int(state.get("total_events", 0)) + 1,
    }

    save_state(next_state)
    return next_state
