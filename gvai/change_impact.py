from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class ChangeImpactInput:
    new_tasks: float = 0.0
    manager_capacity: float = 1.0
    training_readiness: float = 1.0
    clarity: float = 1.0
    recovery_plan_strength: float = 1.0
    active_changes: float = 0.0
    safe_change_limit: float = 1.0


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def evaluate_change_impact(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = ChangeImpactInput(**{
        **asdict(ChangeImpactInput()),
        **{k: v for k, v in payload.items() if k in ChangeImpactInput.__annotations__}
    })

    manager_capacity = max(data.manager_capacity, 0.01)
    safe_change_limit = max(data.safe_change_limit, 0.01)

    risks = {
        "manager_overload": clamp(data.new_tasks / manager_capacity),
        "training_gap": clamp(1 - data.training_readiness),
        "communication_gap": clamp(1 - data.clarity),
        "recovery_gap": clamp(1 - data.recovery_plan_strength),
        "stacking_risk": clamp(data.active_changes / safe_change_limit),
    }

    total_risk = sum(risks.values()) / len(risks)
    gv = clamp(1 - total_risk)

    if gv >= 0.75:
        mode = "ALLOW"
        action = "Proceed with normal monitoring."
    elif gv >= 0.45:
        mode = "QUALIFY"
        action = "Proceed only with reduced burden, clearer communication, and added manager support."
    else:
        mode = "BLOCK"
        action = "Do not roll out yet. The organization is unlikely to absorb this change safely."

    return {
        "gv": round(gv, 3),
        "mode": mode,
        "risk": round(total_risk, 3),
        "risks": {k: round(v, 3) for k, v in risks.items()},
        "judgment": action,
        "principle": "Every new change consumes organizational recovery capacity."
    }
