import csv
from pathlib import Path
import numpy as np

from gvai.gv_formula import rolling_gv_risk

N = 600
WINDOW = 100
RUNS = 100
PROBE_INDICES = [120, 170, 220, 270, 320, 370, 420, 470]
RECOVERY_HORIZON = 300

def rho_at(t):
    return float(np.linspace(0.25, 0.97, N)[min(t, N - 1)])

def simulate_ar(seed):
    rng = np.random.default_rng(seed)
    x = np.zeros(N)

    for t in range(1, N):
        rho = rho_at(t)
        x[t] = rho * x[t - 1] + rng.normal(0, 0.35)

    return x

def rankdata(values):
    order = np.argsort(values)
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(len(values), dtype=float)
    return ranks

def spearman_manual(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)

    if len(a) < 3 or np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return None

    return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])

def theoretical_recovery_time(t):
    rho = max(rho_at(t), 0.01)
    return float(-1.0 / np.log(rho))

def measured_recovery_time(probe_idx):
    rho = rho_at(probe_idx)

    # Start from a standardized unit displacement from equilibrium.
    x = 1.0
    epsilon = 0.01

    deviations = []

    for step in range(1, RECOVERY_HORIZON + 1):
        x = rho * x
        dev = abs(x)
        deviations.append(dev)

        if dev <= epsilon:
            return float(step)

    # Fallback exponential fit
    dev = np.maximum(np.asarray(deviations), 1e-12)
    t = np.arange(len(dev), dtype=float)
    slope = float(np.polyfit(t, np.log(dev), 1)[0])

    if slope < 0:
        return float(1.0 / abs(slope))

    return float(RECOVERY_HORIZON)

rows = []

for seed in range(RUNS):
    x = simulate_ar(seed)
    gv_results = rolling_gv_risk(x, window=WINDOW)
    by_index = {r["index"]: r for r in gv_results}

    for probe_idx in PROBE_INDICES:
        r = by_index.get(probe_idx)
        if r is None:
            continue

        rows.append({
            "seed": seed,
            "probe_index": probe_idx,
            "rho": rho_at(probe_idx),
            "mean_risk": r["mean_risk"],
            "va_risk": r["risks"]["va_risk"],
            "ac_risk": r["risks"]["ac_risk"],
            "measured_recovery_time": measured_recovery_time(probe_idx),
            "theoretical_recovery_time": theoretical_recovery_time(probe_idx),
        })

probe_indices = [r["probe_index"] for r in rows]
mean_risks = [r["mean_risk"] for r in rows]
va_risks = [r["va_risk"] for r in rows]
ac_risks = [r["ac_risk"] for r in rows]
measured = [r["measured_recovery_time"] for r in rows]
theoretical = [r["theoretical_recovery_time"] for r in rows]

summary = {
    "rows": len(rows),
    "probe_index_vs_measured_recovery": spearman_manual(probe_indices, measured),
    "probe_index_vs_theoretical_recovery": spearman_manual(probe_indices, theoretical),
    "mean_risk_vs_measured_recovery": spearman_manual(mean_risks, measured),
    "mean_risk_vs_theoretical_recovery": spearman_manual(mean_risks, theoretical),
    "va_risk_vs_measured_recovery": spearman_manual(va_risks, measured),
    "ac_risk_vs_measured_recovery": spearman_manual(ac_risks, measured),
}

Path("reports").mkdir(exist_ok=True)

with open("reports/gv_perturbation_sanity_rows.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print("✅ Perturbation probe sanity test complete")
print("")
for k, v in summary.items():
    print(f"{k}: {v}")

print("")
print("Saved:")
print("- reports/gv_perturbation_sanity_rows.csv")
