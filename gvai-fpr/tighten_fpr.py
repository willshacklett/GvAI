import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ----------------------------
# CONFIG
# ----------------------------
N_SEEDS = 40
N_STEPS = 140
N_NODES = 60

VAR_THRESHOLD = 0.018
DRIFT_THRESHOLD = 0.0015
PERSIST_STEPS = 4
COLLAPSE_MEAN = 1.55
RECOVERY_WINDOW = 8

np.random.seed(7)

# ----------------------------
# SCENARIOS
# ----------------------------
# stable: should not trigger
# recoverable: noisy + stressed, but recovers
# collapse: sustained deterioration, should trigger with lead time
SCENARIOS = [
    ("stable", 0.45),
    ("recoverable", 0.30),
    ("collapse", 0.25),
]

# ----------------------------
# HELPERS
# ----------------------------
def rolling_mean(values, w):
    out = []
    for i in range(len(values)):
        lo = max(0, i - w + 1)
        out.append(float(np.mean(values[lo:i+1])))
    return np.array(out)

def simulate(seed, scenario):
    rng = np.random.default_rng(seed)

    x = np.ones(N_NODES)
    rows = []

    breach_step = None
    drift_step = None
    collapse_step = None

    persist_count = 0
    drift_count = 0
    sentinel_fired = False

    mean_hist = []
    var_hist = []

    for t in range(N_STEPS):
        # Base dynamics
        base_noise = rng.normal(0.0, 0.008, size=N_NODES)

        if scenario == "stable":
            shock = 0.0
            drift = 0.0
            if 35 <= t <= 45:
                base_noise += rng.normal(0.0, 0.010, size=N_NODES)

        elif scenario == "recoverable":
            shock = 0.0
            drift = 0.0
            if 35 <= t <= 55:
                base_noise += rng.normal(0.0, 0.020, size=N_NODES)
            if 56 <= t <= 80:
                # pull back toward baseline
                x += -0.010 * (x - 1.0)

        elif scenario == "collapse":
            shock = 0.0
            drift = 0.0
            if t >= 35:
                base_noise += rng.normal(0.0, 0.018, size=N_NODES)
            if t >= 60:
                drift = 0.006
            if t >= 80:
                drift = 0.012

        x = x + base_noise + shock + drift

        mean = float(np.mean(x))
        var = float(np.var(x))

        mean_hist.append(mean)
        var_hist.append(var)

        mean_rm = rolling_mean(mean_hist, 6)[-1]
        var_rm = rolling_mean(var_hist, 6)[-1]

        # local slope estimates
        if len(mean_hist) >= 6:
            mean_slope = mean_rm - rolling_mean(mean_hist[:-1], 6)[-1]
            var_slope = var_rm - rolling_mean(var_hist[:-1], 6)[-1]
        else:
            mean_slope = 0.0
            var_slope = 0.0

        # persistence on variance
        if var_rm > VAR_THRESHOLD:
            persist_count += 1
        else:
            persist_count = max(0, persist_count - 1)

        persistent_variance = persist_count >= PERSIST_STEPS

        # drift confirmation on mean
        if mean_slope > DRIFT_THRESHOLD:
            drift_count += 1
        else:
            drift_count = max(0, drift_count - 1)

        drift_confirmed = drift_count >= PERSIST_STEPS

        if breach_step is None and persistent_variance:
            breach_step = t

        if drift_step is None and drift_confirmed:
            drift_step = t

        # sentinel fires only when both are present
        if not sentinel_fired and persistent_variance and drift_confirmed:
            sentinel_fired = True

        if scenario == "collapse" and collapse_step is None and mean >= COLLAPSE_MEAN:
            collapse_step = t

        rows.append({
            "seed": seed,
            "scenario": scenario,
            "t": t,
            "mean": mean,
            "var": var,
            "mean_rm": mean_rm,
            "var_rm": var_rm,
            "mean_slope": mean_slope,
            "var_slope": var_slope,
            "persistent_variance": int(persistent_variance),
            "drift_confirmed": int(drift_confirmed),
            "breach": int(breach_step == t) if breach_step is not None else 0,
            "drift_mark": int(drift_step == t) if drift_step is not None else 0,
            "collapse": int(collapse_step == t) if collapse_step is not None else 0,
            "sentinel_fired": int(sentinel_fired),
        })

    return rows, breach_step, drift_step, collapse_step, sentinel_fired

# ----------------------------
# RUN ALL
# ----------------------------
all_rows = []
summary_rows = []

seed_counter = 0
for scenario, frac in SCENARIOS:
    count = int(round(N_SEEDS * frac))
    for _ in range(count):
        rows, breach_step, drift_step, collapse_step, fired = simulate(seed_counter, scenario)
        all_rows.extend(rows)

        predicted_positive = bool(fired)
        actual_positive = scenario == "collapse"

        lead_time = None
        if breach_step is not None and collapse_step is not None:
            lead_time = collapse_step - breach_step

        summary_rows.append({
            "seed": seed_counter,
            "scenario": scenario,
            "predicted_positive": int(predicted_positive),
            "actual_positive": int(actual_positive),
            "breach_step": breach_step if breach_step is not None else -1,
            "drift_step": drift_step if drift_step is not None else -1,
            "collapse_step": collapse_step if collapse_step is not None else -1,
            "lead_time": lead_time if lead_time is not None else np.nan,
        })
        seed_counter += 1

df = pd.DataFrame(all_rows)
summary = pd.DataFrame(summary_rows)

# ----------------------------
# METRICS
# ----------------------------
tp = int(((summary["predicted_positive"] == 1) & (summary["actual_positive"] == 1)).sum())
tn = int(((summary["predicted_positive"] == 0) & (summary["actual_positive"] == 0)).sum())
fp = int(((summary["predicted_positive"] == 1) & (summary["actual_positive"] == 0)).sum())
fn = int(((summary["predicted_positive"] == 0) & (summary["actual_positive"] == 1)).sum())

tpr = tp / (tp + fn) if (tp + fn) else float("nan")
fpr = fp / (fp + tn) if (fp + tn) else float("nan")
precision = tp / (tp + fp) if (tp + fp) else float("nan")

lead_times = summary.loc[summary["actual_positive"] == 1, "lead_time"].dropna()
lead_mean = float(lead_times.mean()) if len(lead_times) else float("nan")
lead_std = float(lead_times.std(ddof=0)) if len(lead_times) else float("nan")

# ----------------------------
# SAVE CSVs
# ----------------------------
df.to_csv("timeseries.csv", index=False)
summary.to_csv("seed_summary.csv", index=False)

with open("metrics.txt", "w", encoding="utf-8") as f:
    f.write(f"TP={tp}\n")
    f.write(f"TN={tn}\n")
    f.write(f"FP={fp}\n")
    f.write(f"FN={fn}\n")
    f.write(f"TPR={tpr:.4f}\n")
    f.write(f"FPR={fpr:.4f}\n")
    f.write(f"Precision={precision:.4f}\n")
    f.write(f"LeadMean={lead_mean:.4f}\n")
    f.write(f"LeadStd={lead_std:.4f}\n")

# ----------------------------
# AGG CHART
# ----------------------------
collapse_df = df[df["scenario"] == "collapse"].copy()
agg = collapse_df.groupby("t", as_index=False).mean(numeric_only=True)

plt.figure(figsize=(10, 5))
plt.plot(agg["t"], agg["mean_rm"], label="collapse mean (rolling)")
plt.plot(agg["t"], agg["var_rm"], label="collapse variance (rolling)")

breach_pts = collapse_df[collapse_df["breach"] == 1]
collapse_pts = collapse_df[collapse_df["collapse"] == 1]

if not breach_pts.empty:
    plt.scatter(breach_pts["t"], breach_pts["var"], label="breach", marker="o")

if not collapse_pts.empty:
    plt.scatter(collapse_pts["t"], collapse_pts["mean"], label="collapse", marker="x")

plt.title("Recoverability Sentinel: Collapse Cohort")
plt.xlabel("time")
plt.legend()
plt.tight_layout()
plt.savefig("collapse_chart.png", dpi=160)
plt.close()

# ----------------------------
# SCENARIO RATE BAR CHART
# ----------------------------
rate_rows = []
for scenario in summary["scenario"].unique():
    s = summary[summary["scenario"] == scenario]
    rate_rows.append({
        "scenario": scenario,
        "fire_rate": float(s["predicted_positive"].mean())
    })
rates = pd.DataFrame(rate_rows)

plt.figure(figsize=(8, 5))
plt.bar(rates["scenario"], rates["fire_rate"])
plt.title("Sentinel Fire Rate by Scenario")
plt.ylabel("fire rate")
plt.tight_layout()
plt.savefig("fire_rate_chart.png", dpi=160)
plt.close()

# ----------------------------
# CONSOLE OUTPUT
# ----------------------------
print("Saved: timeseries.csv")
print("Saved: seed_summary.csv")
print("Saved: metrics.txt")
print("Saved: collapse_chart.png")
print("Saved: fire_rate_chart.png")
print()
print(f"TP={tp} TN={tn} FP={fp} FN={fn}")
print(f"TPR={tpr:.4f}")
print(f"FPR={fpr:.4f}")
print(f"Precision={precision:.4f}")
print(f"LeadMean={lead_mean:.4f}")
print(f"LeadStd={lead_std:.4f}")
