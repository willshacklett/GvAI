from __future__ import annotations

from typing import Any, Dict


def decide_intervention(state: Dict[str, Any]) -> Dict[str, Any]:
    mode = state.get("trajectory_mode", "UNKNOWN")
    rolling_gv = state.get("rolling_gv")
    drift_trend = float(state.get("drift_trend", 0.0) or 0.0)
    recoverability_trend = float(state.get("recoverability_trend", 0.0) or 0.0)

    level = "NONE"
    decision = "continue"
    actions = ["Continue normal operation."]

    if mode == "WATCH":
        level = "SOFT"
        decision = "qualify"
        actions = [
            "Add constraints.",
            "Verify assumptions.",
            "Keep rollback available.",
            "Monitor next response for drift."
        ]

    if mode == "DEGRADING":
        level = "HARD"
        decision = "intervene"
        actions = [
            "Require verification before action.",
            "Require rollback plan.",
            "Reduce autonomy.",
            "Prefer reversible next step.",
            "Escalate review if risk persists."
        ]

    if rolling_gv is not None and float(rolling_gv) < 0.55:
        level = "HARD"
        decision = "intervene"
        actions.append("Rolling GV below safe threshold.")

    if drift_trend > 0.10:
        level = "HARD"
        decision = "intervene"
        actions.append("Drift trend is rising.")

    if recoverability_trend > 0.10:
        level = "HARD"
        decision = "intervene"
        actions.append("Recoverability risk is rising.")

    return {
        "intervention_level": level,
        "decision": decision,
        "trajectory_mode": mode,
        "rolling_gv": rolling_gv,
        "drift_trend": drift_trend,
        "recoverability_trend": recoverability_trend,
        "actions": actions,
    }
