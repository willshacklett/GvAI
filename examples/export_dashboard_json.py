import json
import numpy as np
from gvai import run_sentinel_series, summarize_timeline

N_STEPS = 140
N_NODES = 60

def make_series(seed: int = 42, scenario: str = "collapse"):
    rng = np.random.default_rng(seed)
    x = np.ones(N_NODES)
    series = []

    for t in range(N_STEPS):
        noise = rng.normal(0.0, 0.008, size=N_NODES)

        if scenario == "stable":
            if 35 <= t <= 45:
                noise += rng.normal(0.0, 0.010, size=N_NODES)
            drift = 0.0

        elif scenario == "recoverable":
            if 35 <= t <= 55:
                noise += rng.normal(0.0, 0.020, size=N_NODES)
            drift = 0.0
            if 56 <= t <= 80:
                x += -0.010 * (x - 1.0)

        elif scenario == "collapse":
            if t >= 35:
                noise += rng.normal(0.0, 0.018, size=N_NODES)
            drift = 0.0
            if t >= 60:
                drift = 0.006
            if t >= 80:
                drift = 0.012
        else:
            raise ValueError("bad scenario")

        x = x + noise + drift
        series.append(x.copy())

    return series

scenario = "collapse"
result = run_sentinel_series(make_series(scenario=scenario))
summary = summarize_timeline(result)

payload = {
    "scenario": scenario,
    "result": {
        "status": result["status"],
        "fired": result["fired"],
        "breach_step": result["breach_step"],
        "drift_step": result["drift_step"],
        "collapse_step": result["collapse_step"],
        "lead_time": result["lead_time"],
        "reasons": result["reasons"],
    },
    "summary": summary,
    "timeline": result["timeline"],
}

with open("data/sentinel_output.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

print("Saved data/sentinel_output.json")
