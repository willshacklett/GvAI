import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

np.random.seed(42)

# ---- CONFIG ----
N_STEPS = 120
N_SEEDS = 20
VAR_THRESHOLD = 0.015
DRIFT_THRESHOLD = 0.002

results = []

def simulate(seed):
    np.random.seed(seed)

    x = np.ones(50)
    history = []

    breached = False
    breach_step = None
    collapse_step = None

    for t in range(N_STEPS):
        noise = np.random.normal(0, 0.01, size=x.shape)

        # gradual destabilization
        if t > 40:
            noise += np.random.normal(0, 0.02, size=x.shape)

        if t > 70:
            x += np.random.normal(0.01, 0.02, size=x.shape)

        x = x + noise

        mean = np.mean(x)
        var = np.var(x)

        history.append((t, mean, var))

        # breach condition
        if not breached and var > VAR_THRESHOLD:
            breached = True
            breach_step = t

        # collapse condition
        if breached and mean > 1.5:
            collapse_step = t
            break

    return history, breach_step, collapse_step


all_histories = []

for seed in range(N_SEEDS):
    hist, breach, collapse = simulate(seed)

    for t, m, v in hist:
        all_histories.append({
            "seed": seed,
            "t": t,
            "mean": m,
            "var": v,
            "breach": int(t == breach) if breach else 0,
            "collapse": int(t == collapse) if collapse else 0
        })

df = pd.DataFrame(all_histories)

# ---- AGGREGATE ----
agg = df.groupby("t").mean(numeric_only=True).reset_index()

# ---- PLOT ----
plt.figure(figsize=(10,5))

plt.plot(agg["t"], agg["mean"], label="mean")
plt.plot(agg["t"], agg["var"], label="variance")

# mark breach
breach_points = df[df["breach"] == 1]
collapse_points = df[df["collapse"] == 1]

if not breach_points.empty:
    plt.scatter(breach_points["t"], breach_points["var"],
                label="breach", marker="o")

if not collapse_points.empty:
    plt.scatter(collapse_points["t"], collapse_points["mean"],
                label="collapse", marker="x")

plt.title("Multi-seed Recoverability Signal")
plt.xlabel("time")
plt.legend()
plt.tight_layout()

plt.savefig("chart.png")
print("Saved chart.png")

# ---- METRICS ----
lead_times = []

for seed in range(N_SEEDS):
    s = df[df["seed"] == seed]
    b = s[s["breach"] == 1]["t"]
    c = s[s["collapse"] == 1]["t"]

    if not b.empty and not c.empty:
        lead_times.append(c.iloc[0] - b.iloc[0])

if lead_times:
    print("Mean Δt:", np.mean(lead_times))
    print("Std Δt:", np.std(lead_times))
else:
    print("No valid lead times detected")
