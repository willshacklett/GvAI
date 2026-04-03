import json
from typing import Dict, Any
import numpy as np

from gvai import run_sentinel_series


def compute_godscore(result: Dict[str, Any]) -> int:
    status = result.get("status", "stable")
    lead_time = result.get("lead_time")
    fired = bool(result.get("fired", False))

    base = 100

    if status == "warning":
        base = 75
    elif status == "critical":
        base = 40
    elif status == "collapse":
        base = 5

    if fired:
        base -= 5

    if lead_time is not None:
        # more lead time is better than instant collapse, but still penalize non-stable states
        if lead_time >= 30:
            base += 5
        elif lead_time <= 10:
            base -= 10

    return max(0, min(100, int(base)))


def evaluate_series(
    series,
    *,
    fail_on_critical: bool = True,
    fail_on_warning: bool = False,
) -> Dict[str, Any]:
    result = run_sentinel_series(series)

    status = result["status"]
    godscore = compute_godscore(result)

    passed = True
    if status == "collapse":
        passed = False
    elif status == "critical" and fail_on_critical:
        passed = False
    elif status == "warning" and fail_on_warning:
        passed = False

    payload = {
        "godscore": godscore,
        "status": status,
        "passed": passed,
        "fired": result["fired"],
        "breach_step": result["breach_step"],
        "drift_step": result["drift_step"],
        "collapse_step": result["collapse_step"],
        "lead_time": result["lead_time"],
        "reasons": result["reasons"],
    }
    return payload


def save_result(payload: Dict[str, Any], path: str = "ci_result.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


if __name__ == "__main__":
    # tiny self-demo
    rng = np.random.default_rng(42)
    x = np.ones(60)
    series = []

    for t in range(140):
        noise = rng.normal(0.0, 0.008, size=60)
        if t >= 35:
            noise += rng.normal(0.0, 0.018, size=60)
        drift = 0.0
        if t >= 60:
            drift = 0.006
        if t >= 80:
            drift = 0.012
        x = x + noise + drift
        series.append(x.copy())

    payload = evaluate_series(series)
    save_result(payload)
    print(json.dumps(payload, indent=2))
