from __future__ import annotations

from typing import Any, Dict

from gvai.kernel.trajectory import load_state
from gvai.kernel.intervention import decide_intervention


def observatory_snapshot() -> Dict[str, Any]:
    trajectory = load_state()
    intervention = decide_intervention(trajectory)

    events = trajectory.get("events", [])
    latest = events[-1] if events else None

    return {
        "kernel_version": "0.1",
        "status": "online",
        "rolling_gv": trajectory.get("rolling_gv"),
        "trajectory_mode": trajectory.get("trajectory_mode"),
        "drift_trend": trajectory.get("drift_trend"),
        "recoverability_trend": trajectory.get("recoverability_trend"),
        "total_events": trajectory.get("total_events"),
        "intervention_level": intervention.get("intervention_level"),
        "intervention_decision": intervention.get("decision"),
        "intervention_actions": intervention.get("actions", []),
        "latest_event": latest,
        "interpretation": "GV is monitoring whether intelligence remains recoverable over time.",
    }
