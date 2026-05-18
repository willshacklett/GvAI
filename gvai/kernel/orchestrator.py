from __future__ import annotations

from typing import Any, Dict, List

from gvai.kernel.runtime import score_runtime
from gvai.kernel.trajectory import update_state
from gvai.kernel.intervention import decide_intervention
from gvai.kernel.arbitration import arbitrate


def run_kernel(
    user_message: str = "",
    candidate_response: str = "",
    candidates: List[Dict[str, Any]] | None = None,
    context: str = "kernel-orchestrator",
) -> Dict[str, Any]:
    runtime = score_runtime(
        user_message=user_message,
        candidate_response=candidate_response,
        context=context,
    )

    trajectory = update_state(runtime, label=context)
    intervention = decide_intervention(trajectory)

    arbitration = None
    if candidates:
        arbitration = arbitrate(
            user_message=user_message,
            candidates=candidates,
            context=f"{context}:arbitration",
        )

    return {
        "kernel_version": "0.1",
        "runtime": runtime,
        "trajectory": trajectory,
        "intervention": intervention,
        "arbitration": arbitration,
        "output_decision": {
            "gv": runtime.get("gv"),
            "mode": runtime.get("gv_mode"),
            "action": runtime.get("gv_action"),
            "intervention_level": intervention.get("intervention_level"),
            "decision": intervention.get("decision"),
        },
    }
