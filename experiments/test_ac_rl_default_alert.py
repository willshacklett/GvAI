import json
import numpy as np

from gvai.gv_formula import rolling_gv_risk

N = 600
WINDOW = 100
COLLAPSE_INDEX = 420
RUNS = 100

def ar_degrade(seed):
    rng = np.random.default_rng(seed)
    x = np.zeros(N)
    rho_values = np.linspace(0.25, 0.97, N)

    for t in range(1, N):
        noise = rng.normal(0, 0.35)
        if t > 350:
            noise *= 1 + (t - 350) / 100
        drift = 0.015 * max(0, t - COLLAPSE_INDEX)
        x[t] = rho_values[t] * x[t - 1] + noise + drift

    return x

leads = []

for seed in range(RUNS):
    x = ar_degrade(seed)
    results = rolling_gv_risk(x, window=WINDOW)
    first = next((r for r in results if r["gv_alerts"]["recommended_alert"]), None)
    if first:
        leads.append(COLLAPSE_INDEX - first["index"])

summary = {
    "runs": RUNS,
    "detections": len(leads),
    "detection_rate": len(leads) / RUNS,
    "median_lead_time": float(np.median(leads)) if leads else None,
    "mean_lead_time": float(np.mean(leads)) if leads else None,
    "min_lead_time": float(np.min(leads)) if leads else None,
    "max_lead_time": float(np.max(leads)) if leads else None,
}

print("✅ AC/RL default alert test complete")
print(json.dumps(summary, indent=2))
