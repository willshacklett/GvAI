import csv
from pathlib import Path
import numpy as np

from gvai.gv_formula import rolling_gv_risk

N = 600
WINDOW = 100
RUNS = 100
COLLAPSE_INDEX = 420
THRESHOLDS = np.arange(0.30, 0.91, 0.05)

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

    return x, True

def volatility_null(seed):
    rng = np.random.default_rng(seed)
    x = np.zeros(N)

    for t in range(1, N):
        noise_scale = 0.25 + 0.45 * (t / N)
        x[t] = 0.30 * x[t - 1] + rng.normal(0, noise_scale)

    return x, False

def trend_null(seed):
    rng = np.random.default_rng(seed)
    x = np.zeros(N)

    for t in range(1, N):
        x[t] = 0.35 * x[t - 1] + rng.normal(0, 0.35) + 0.002 * t

    return x, False

SYSTEMS = {
    "ar_degrade": ar_degrade,
    "volatility_null": volatility_null,
    "trend_null": trend_null,
}

def score_row(r):
    ac = r["risks"]["ac_risk"]
    rl = r["risks"]["rl_risk"]

    return {
        "mean_risk": r["mean_risk"],
        "recovery_core_risk": r.get("recovery_core_risk", None),
        "ac_risk": ac,
        "rl_risk": rl,
        "ac_rl_core": float(0.5 * ac + 0.5 * rl),
        "va_risk": r["risks"]["va_risk"],
    }

def first_cross(series, metric, threshold):
    for row in series:
        value = row[metric]
        if value is not None and value >= threshold:
            return row["index"]
    return None

rows = []

for system_name, sim in SYSTEMS.items():
    for seed in range(RUNS):
        x, has_collapse = sim(seed)
        results = rolling_gv_risk(x, window=WINDOW)

        series = []
        for r in results:
            series.append({
                "index": r["index"],
                **score_row(r),
            })

        for metric in ["mean_risk", "recovery_core_risk", "ac_rl_core", "ac_risk", "rl_risk", "va_risk"]:
            for threshold in THRESHOLDS:
                idx = first_cross(series, metric, threshold)

                if has_collapse:
                    lead = None if idx is None else COLLAPSE_INDEX - idx
                    detected_before = idx is not None and idx < COLLAPSE_INDEX
                    false_positive = False
                else:
                    lead = None
                    detected_before = False
                    false_positive = idx is not None

                rows.append({
                    "system": system_name,
                    "seed": seed,
                    "has_collapse": has_collapse,
                    "metric": metric,
                    "threshold": round(float(threshold), 2),
                    "alert_index": idx,
                    "lead_time": lead,
                    "detected_before_collapse": detected_before,
                    "false_positive": false_positive,
                })

summary = []

for system_name in SYSTEMS:
    for metric in ["mean_risk", "recovery_core_risk", "ac_rl_core", "ac_risk", "rl_risk", "va_risk"]:
        for threshold in THRESHOLDS:
            subset = [
                r for r in rows
                if r["system"] == system_name
                and r["metric"] == metric
                and r["threshold"] == round(float(threshold), 2)
            ]

            has_collapse = subset[0]["has_collapse"]

            if has_collapse:
                leads = [r["lead_time"] for r in subset if r["lead_time"] is not None]
                before = [r for r in subset if r["detected_before_collapse"]]

                fp_rate = None
                utility = None
                if leads:
                    median_lead = float(np.median(leads))
                    utility = median_lead * (len(before) / RUNS)
                else:
                    median_lead = None

                summary.append({
                    "system": system_name,
                    "metric": metric,
                    "threshold": round(float(threshold), 2),
                    "type": "collapse",
                    "detection_rate_before_collapse": len(before) / RUNS,
                    "false_positive_rate": fp_rate,
                    "median_lead_time": median_lead,
                    "utility": utility,
                })
            else:
                fps = [r for r in subset if r["false_positive"]]
                summary.append({
                    "system": system_name,
                    "metric": metric,
                    "threshold": round(float(threshold), 2),
                    "type": "null",
                    "detection_rate_before_collapse": None,
                    "false_positive_rate": len(fps) / RUNS,
                    "median_lead_time": None,
                    "utility": None,
                })

Path("reports").mkdir(exist_ok=True)

with open("reports/gv_ac_rl_core_ood_rows.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

with open("reports/gv_ac_rl_core_ood_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=summary[0].keys())
    writer.writeheader()
    writer.writerows(summary)

print("✅ AC/RL core OOD comparison complete")
print("")
print("Best AR-degrade candidates with trend_null + volatility_null FP <= 0.10:")

candidates = []
for s in summary:
    if s["system"] != "ar_degrade" or s["type"] != "collapse":
        continue

    metric = s["metric"]
    threshold = s["threshold"]

    null_fps = [
        n["false_positive_rate"]
        for n in summary
        if n["metric"] == metric
        and n["threshold"] == threshold
        and n["type"] == "null"
    ]

    if null_fps and max(null_fps) <= 0.10 and s["utility"] is not None:
        candidates.append({
            **s,
            "max_null_fp": max(null_fps),
        })

candidates.sort(key=lambda x: x["utility"], reverse=True)

for c in candidates[:20]:
    print(
        f'{c["metric"]} @ {c["threshold"]}: '
        f'detect={c["detection_rate_before_collapse"]:.2f}, '
        f'median_lead={c["median_lead_time"]}, '
        f'max_null_fp={c["max_null_fp"]:.2f}, '
        f'utility={c["utility"]:.2f}'
    )

print("")
print("Saved:")
print("- reports/gv_ac_rl_core_ood_rows.csv")
print("- reports/gv_ac_rl_core_ood_summary.csv")
