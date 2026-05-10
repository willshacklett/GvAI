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

def true_recovery_time(t):
    rho = max(rho_at(t), 0.01)
    return float(-1.0 / np.log(rho))

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
            "ac_risk": r["risks"]["ac_risk"],
            "rl_risk": r["risks"]["rl_risk"],
            "mean_risk": r["mean_risk"],
            "ac_rl_equal": 0.5 * r["risks"]["ac_risk"] + 0.5 * r["risks"]["rl_risk"],
        })

y = np.asarray([r["true_recovery_time"] for r in rows], dtype=float)
X = np.asarray([[r["ac_risk"], r["rl_risk"]] for r in rows], dtype=float)

# Standardize X for stable regression.
X_mean = X.mean(axis=0)
X_std = X.std(axis=0)
Xz = (X - X_mean) / np.where(X_std == 0, 1, X_std)

# Fit linear model to true recovery.
X_design = np.column_stack([np.ones(len(Xz)), Xz])
coef, *_ = np.linalg.lstsq(X_design, y, rcond=None)

raw_weights = np.abs(coef[1:])
if raw_weights.sum() == 0:
    weights = np.array([0.5, 0.5])
else:
    weights = raw_weights / raw_weights.sum()

w_ac = float(weights[0])
w_rl = float(weights[1])

for r in rows:
    r["ac_rl_fitted"] = w_ac * r["ac_risk"] + w_rl * r["rl_risk"]

metrics = [
    "ac_risk",
    "rl_risk",
    "ac_rl_equal",
    "ac_rl_fitted",
    "mean_risk",
]

summary = []
for m in metrics:
    vals = [r[m] for r in rows]
    summary.append({
        "metric": m,
        "spearman_vs_true_recovery": spearman(vals, y),
    })

summary.append({
    "metric": "fitted_weight_ac",
    "spearman_vs_true_recovery": w_ac,
})
summary.append({
    "metric": "fitted_weight_rl",
    "spearman_vs_true_recovery": w_rl,
})

Path("reports").mkdir(exist_ok=True)

with open("reports/gv_ac_rl_weight_fit_rows.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

with open("reports/gv_ac_rl_weight_fit_summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=summary[0].keys())
    writer.writeheader()
    writer.writerows(summary)

print("✅ AC/RL weight fit complete")
print("")
print(f"Fitted weights: AC={w_ac:.3f}, RL={w_rl:.3f}")
print("")
for r in sorted(summary[:-2], key=lambda x: x["spearman_vs_true_recovery"], reverse=True):
    print(f'{r["metric"]}: {r["spearman_vs_true_recovery"]}')

print("")
print("Saved:")
print("- reports/gv_ac_rl_weight_fit_rows.csv")
print("- reports/gv_ac_rl_weight_fit_summary.csv")
