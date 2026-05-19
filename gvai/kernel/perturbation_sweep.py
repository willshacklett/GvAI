from __future__ import annotations

from typing import Any, Dict, List

from gvai.kernel.protocol import build_gv_heartbeat
from gvai.kernel.phase_timeline import update_timeline, reset_timeline
from gvai.kernel.phase_lock import detect_phase_lock
from gvai.kernel.recovery_half_life import estimate_recovery_half_life


def _phase_from_debt(debt: float) -> str:
    if debt >= 6.0:
        return "COLLAPSE_ZONE"
    if debt >= 3.0:
        return "CASCADE_RISK"
    if debt >= 1.5:
        return "DEGRADING"
    if debt >= 0.5:
        return "TURBULENT"
    return "ELASTIC"


def run_perturbation_sweep(
    steps: int = 12,
    perturbation_strength: float = 0.25,
    recovery_rate: float = 0.15,
    arbitration_depth: int = 0,
    reset: bool = True,
) -> Dict[str, Any]:

    if reset:
        reset_timeline()

    debt = 0.0
    events: List[Dict[str, Any]] = []

    for step in range(steps):
        perturbation = perturbation_strength

        arbitration_mask = arbitration_depth * 0.03

        recovery = recovery_rate * max(0.0, 1.0 - debt / 10.0)

        debt = max(
            0.0,
            debt + perturbation - recovery + arbitration_mask
        )

        debt = round(min(debt, 10.0), 3)

        elasticity = round(max(0.0, 1.0 - debt / 10.0), 3)

        phase_name = _phase_from_debt(debt)

        visible_coherence = round(
            max(0.0, min(1.0, 1.0 - (debt / 12.0) + arbitration_depth * 0.04)),
            3,
        )

        heartbeat = build_gv_heartbeat(
            runtime={"gv": round(elasticity, 3)},
            debt={
                "debt": debt,
                "elasticity": elasticity,
                "debt_velocity": perturbation,
            },
            phase={"phase": phase_name},
            visible_coherence=visible_coherence,
            context="perturbation-sweep",
        )

        timeline = update_timeline(heartbeat)

        events.append({
            "step": step,
            "debt": debt,
            "elasticity": elasticity,
            "phase": phase_name,
            "visible_coherence": visible_coherence,
            "masking_distance": heartbeat["masking_distance"],
            "heartbeat": heartbeat,
        })

    lock = detect_phase_lock(timeline)
    half_life = estimate_recovery_half_life(timeline)

    return {
        "steps": steps,
        "perturbation_strength": perturbation_strength,
        "recovery_rate": recovery_rate,
        "arbitration_depth": arbitration_depth,
        "events": events,
        "final_timeline": timeline,
        "phase_lock": lock,
        "recovery_half_life": half_life,
    }
