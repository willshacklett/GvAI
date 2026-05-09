import csv
from pathlib import Path
import numpy as np

from gvai.gv_formula import rolling_gv_risk

N = 600
WINDOW = 100
RUNS = 100
PROBE_INDICES = [120, 170, 220, 270, 320, 370, 420, 470]

def rho_at(t):
    return float(np.linspace(0.25, 0.97, N)[min(t, N - 1)])

def simulate_ar(seed):
    rng = np.random.default_rng(seed)
    x = np.zeros(N)
    for t in range(1, N):
        x[t] = rho_at(t) * x[t - 1] + rng.normal(0, 0.35)
    return x

def rankdata(values):
    order = np.argsort(values)
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(len(values), dtype=float)
    return ranks

def spearman(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) < 3 or np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return None
    return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])

def true_recovery_time(t):
    rho = max(rho_at(t), 0.01)
    return float(-1.0 / np.log(rho))

rows = []

for seed in range(RUNS):
    x = simulate_ar(seed)
    results = rolling_gv_risk(x, window=WINDOW)
    by_idx = {r["index"]: r for r in results}

    for probe in PROBE_INDICES:
        r = by_idx.get(probe)
        if not r:
            continue

        rows.append({
            "seed": seed,
            "probe_index": probe,
            "true_recovery_time": true_recovery_time(probe),
            "mean_risk": r["mean_risk"],
            "recovery_core_risk": r["recovery_core_risk"],
            "ac_risk": r["risks"]["ac_risk"],
            "rl_risk": r["risks"]["rl_risk"],
            "pr_risk": r["risks"]["pr_risk"],
            "va_risk": r["risks"]["va_risk"],
            "bd_risk": r["risks"]["bd_risk"],
        })

target = [r["true_recovery_time"] for r in rows]

metrics = [
    "mean_risk",
    "recovery_core_risk",
    "ac_risk",
    "rl_risk",
    "pr_risk",
    "va_risk",
    "bd_risk",
]

summary_rows = []
for m in metrics:
    vals = [r[m] for r in rows]
    summary_rows.append({
        "metric": m,
        "spearman_vs_true_recovery": spearman(vals, target),
    })

Path("reports").mkdir(exist_ok=True)

with open("reports/gv_recovery_core_rows.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

with open("reports/gv_recovery_core_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
    writer.writeheader()
    writer.writerows(summary_rows)

print("✅ Recovery core test complete")
print("")
for r in sorted(summary_rows, key=lambda x: x["spearman_vs_true_recovery"], reverse=True):
    print(f'{r["metric"]}: {r["spearman_vs_true_recovery"]}')

print("")
print("Saved:")
print("- reports/gv_recovery_core_rows.csv")
print("- reports/gv_recovery_core_summary.csv")
