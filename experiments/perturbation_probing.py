import csv
from pathlib import Path
import numpy as np

from gvai.gv_formula import rolling_gv_risk

N = 600
WINDOW = 100
RUNS = 50
COLLAPSE_INDEX = 420
PROBE_INDICES = [120, 170, 220, 270, 320, 370, 420, 470]
RECOVERY_HORIZON = 200

def ar_params(t):
    rho = np.linspace(0.25, 0.97, N)[min(t, N - 1)]
    noise_scale = 0.35
    if t > 350:
        noise_scale *= 1 + (t - 350) / 100
    drift = 0.015 * max(0, t - COLLAPSE_INDEX)
    return rho, noise_scale, drift

def simulate_ar_degrade(seed):
    rng = np.random.default_rng(seed)
    x = np.zeros(N)

    for t in range(1, N):
        rho, noise_scale, drift = ar_params(t)
        x[t] = rho * x[t - 1] + rng.normal(0, noise_scale) + drift

    return x

def rankdata(values):
    order = np.argsort(values)
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(len(values), dtype=float)
    return ranks

def spearman_manual(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)

    if len(a) < 3:
        return None

    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return None

    ra = rankdata(a)
    rb = rankdata(b)

    return float(np.corrcoef(ra, rb)[0, 1])

def measure_recovery_after_perturbation(seed, probe_idx, pre_series):
    rng = np.random.default_rng(seed + 100000 + probe_idx)

    window = pre_series[max(0, probe_idx - WINDOW):probe_idx]
    if len(window) < 10:
        return None

    attractor = float(np.mean(window))
    std = float(np.std(window))
    if std < 1e-9:
        std = 1e-9

    x = float(pre_series[probe_idx - 1])

    # Push away from attractor.
    direction = 1.0 if x >= attractor else -1.0
    shock = direction * 0.08 * std
    x = x + shock

    epsilon = 0.01 * std
    stable_count = 0

    deviations = []

    for step in range(1, RECOVERY_HORIZON + 1):
        t = min(probe_idx + step, N - 1)
        rho, noise_scale, drift = ar_params(t)

        # Use reduced noise during recovery probe so recovery can be measured.
        x = rho * x + rng.normal(0, noise_scale * 0.25) + drift

        deviation = abs(x - attractor)
        deviations.append(deviation)

        if deviation <= epsilon:
            stable_count += 1
            if stable_count >= 5:
                return step - 4
        else:
            stable_count = 0

    # Fallback: fit exponential decay over observed return trajectory.
    dev = np.asarray(deviations, dtype=float)
    dev = np.maximum(dev, 1e-9)

    t = np.arange(len(dev), dtype=float)
    slope = float(np.polyfit(t, np.log(dev), 1)[0])

    if slope < 0:
        return float(1.0 / abs(slope))

    return float(RECOVERY_HORIZON)

def main():
    rows = []
    per_seed_stats = []

    for seed in range(RUNS):
        x = simulate_ar_degrade(seed)
        gv_results = rolling_gv_risk(x, window=WINDOW)
        by_index = {r["index"]: r for r in gv_results}

        gvs = []
        r_trues = []

        for probe_idx in PROBE_INDICES:
            gv_row = by_index.get(probe_idx)
            if gv_row is None:
                continue

            true_recovery = measure_recovery_after_perturbation(seed, probe_idx, x)

            if true_recovery is None:
                continue

            mean_risk = gv_row["mean_risk"]
            va_risk = gv_row["risks"]["va_risk"]
            ac_risk = gv_row["risks"]["ac_risk"]

            gvs.append(mean_risk)
            r_trues.append(true_recovery)

            rows.append({
                "seed": seed,
                "probe_index": probe_idx,
                "mean_risk": mean_risk,
                "va_risk": va_risk,
                "ac_risk": ac_risk,
                "true_recovery_time": true_recovery,
            })

        rho = spearman_manual(gvs, r_trues)

        per_seed_stats.append({
            "seed": seed,
            "spearman_mean_risk_vs_recovery": rho,
            "num_probes": len(gvs),
        })

    all_mean = [r["mean_risk"] for r in rows]
    all_va = [r["va_risk"] for r in rows]
    all_ac = [r["ac_risk"] for r in rows]
    all_recovery = [r["true_recovery_time"] for r in rows]

    overall_mean_rho = spearman_manual(all_mean, all_recovery)
    overall_va_rho = spearman_manual(all_va, all_recovery)
    overall_ac_rho = spearman_manual(all_ac, all_recovery)

    valid_seed_rhos = [
        r["spearman_mean_risk_vs_recovery"]
        for r in per_seed_stats
        if r["spearman_mean_risk_vs_recovery"] is not None
    ]

    summary = {
        "runs": RUNS,
        "total_probe_rows": len(rows),
        "overall_spearman_mean_risk_vs_true_recovery": overall_mean_rho,
        "overall_spearman_va_risk_vs_true_recovery": overall_va_rho,
        "overall_spearman_ac_risk_vs_true_recovery": overall_ac_rho,
        "median_seed_spearman_mean_risk": float(np.median(valid_seed_rhos)) if valid_seed_rhos else None,
        "mean_seed_spearman_mean_risk": float(np.mean(valid_seed_rhos)) if valid_seed_rhos else None,
    }

    Path("reports").mkdir(exist_ok=True)

    with open("reports/gv_perturbation_probe_rows.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    with open("reports/gv_perturbation_probe_seed_stats.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=per_seed_stats[0].keys())
        writer.writeheader()
        writer.writerows(per_seed_stats)

    print("✅ Gv perturbation probing complete")
    print("")
    for k, v in summary.items():
        print(f"{k}: {v}")

    print("")
    print("Saved:")
    print("- reports/gv_perturbation_probe_rows.csv")
    print("- reports/gv_perturbation_probe_seed_stats.csv")

if __name__ == "__main__":
    main()
