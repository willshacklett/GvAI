import csv
import itertools
from pathlib import Path
import numpy as np

from gvai.gv_formula import rolling_gv_risk

N = 600
WINDOW = 100
RUNS = 100
COLLAPSE_INDEX = 420

COMPONENTS = [
    "ac_risk",
    "rl_risk",
    "va_risk",
    "pr_risk",
    "bd_risk",
]

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

    return x

def volatility_null(seed):
    rng = np.random.default_rng(seed)
    x = np.zeros(N)

    for t in range(1, N):
        noise_scale = 0.25 + 0.45 * (t / N)
        x[t] = 0.30 * x[t - 1] + rng.normal(0, noise_scale)

    return x

def component_score(result, subset):
    return float(np.mean([result["risks"][c] for c in subset]))

def first_cross(results, subset, threshold):
    for r in results:
        if component_score(r, subset) >= threshold:
            return r["index"]
    return None

subsets = []
for r in range(1, len(COMPONENTS) + 1):
    subsets.extend(itertools.combinations(COMPONENTS, r))

print("Precomputing runs...")
degrade_runs = [rolling_gv_risk(ar_degrade(seed), window=WINDOW) for seed in range(RUNS)]
null_runs = [rolling_gv_risk(volatility_null(seed), window=WINDOW) for seed in range(RUNS)]

rows = []

for subset in subsets:
    subset_name = "+".join(subset)

    for threshold in THRESHOLDS:
        leads = []
        detections = 0

        for run in degrade_runs:
            idx = first_cross(run, subset, threshold)
            if idx is not None:
                detections += 1
                leads.append(COLLAPSE_INDEX - idx)

        fps = 0
        for run in null_runs:
            idx = first_cross(run, subset, threshold)
            if idx is not None:
                fps += 1

        detect_rate = detections / RUNS
        fp_rate = fps / RUNS

        median_lead = float(np.median(leads)) if leads else None
        mean_lead = float(np.mean(leads)) if leads else None
        std_lead = float(np.std(leads)) if leads else None

        utility = None
        if median_lead is not None:
            utility = median_lead * max(0.0, 1.0 - fp_rate)

        rows.append({
            "subset": subset_name,
            "num_components": len(subset),
            "threshold": round(float(threshold), 2),
            "detect_rate": detect_rate,
            "false_positive_rate": fp_rate,
            "median_lead_time": median_lead,
            "mean_lead_time": mean_lead,
            "std_lead_time": std_lead,
            "utility": utility,
        })

rows_sorted = sorted(
    rows,
    key=lambda r: -999999 if r["utility"] is None else -r["utility"]
)

top = rows_sorted[:25]

Path("reports").mkdir(exist_ok=True)

with open("reports/gv_ablation_results.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

with open("reports/gv_ablation_top25.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=top[0].keys())
    writer.writeheader()
    writer.writerows(top)

print("✅ Gv ablation study complete")
print("")
print("Top 25 configurations:")
print("")

for r in top:
    print(
        f'{r["subset"]} | '
        f'n={r["num_components"]} | '
        f't={r["threshold"]:.2f} | '
        f'detect={r["detect_rate"]:.2f} | '
        f'fp={r["false_positive_rate"]:.2f} | '
        f'median_lead={r["median_lead_time"]} | '
        f'std={r["std_lead_time"]:.2f} | '
        f'utility={r["utility"]:.2f}'
    )

print("")
print("Saved:")
print("- reports/gv_ablation_results.csv")
print("- reports/gv_ablation_top25.csv")
