import csv
from pathlib import Path
import numpy as np

INPUT = Path("reports/gv_external_traces/messy_queue_pressure.normalized.csv")
OUT = Path("reports/gv_google_cluster/google_cluster_transition_pass.csv")

BASELINE_WINDOW = 8
WARNING_THRESHOLD = 0.70


def load_rows(path):
    rows = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "time": float(row["time"]),
                "value": float(row["value"]),
            })
    return rows


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def transition_scores(values):
    values = np.array(values, dtype=float)
    scores = []
    slopes = []
    accelerations = []

    for i in range(len(values)):
        if i < BASELINE_WINDOW * 2:
            scores.append(1.0)
            slopes.append(0.0)
            accelerations.append(0.0)
            continue

        recent = values[i - BASELINE_WINDOW:i]
        prior = values[i - (BASELINE_WINDOW * 2):i - BASELINE_WINDOW]

        recent_slope = float(np.mean(np.diff(recent))) if len(recent) > 1 else 0.0
        prior_slope = float(np.mean(np.diff(prior))) if len(prior) > 1 else 0.0
        acceleration = recent_slope - prior_slope

        local_std = float(np.std(values[max(0, i - BASELINE_WINDOW * 2):i])) or 1.0

        slope_pressure = clamp01(max(0.0, recent_slope) / max(1.0, local_std))
        acceleration_pressure = clamp01(max(0.0, acceleration) / max(1.0, local_std))

        transition_pressure = 0.45 * slope_pressure + 0.55 * acceleration_pressure
        gv = 1.0 - transition_pressure

        scores.append(round(clamp01(gv), 4))
        slopes.append(round(recent_slope, 4))
        accelerations.append(round(acceleration, 4))

    return scores, slopes, accelerations


def main():
    rows = load_rows(INPUT)
    values = [r["value"] for r in rows]

    gv, slopes, accelerations = transition_scores(values)
    hits = {i for i, g in enumerate(gv) if g < WARNING_THRESHOLD}

    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "time",
                "value",
                "slope",
                "acceleration",
                "gv_transition",
                "candidate_transition",
            ],
        )
        writer.writeheader()

        for i, row in enumerate(rows):
            writer.writerow({
                "time": row["time"],
                "value": row["value"],
                "slope": slopes[i],
                "acceleration": accelerations[i],
                "gv_transition": gv[i],
                "candidate_transition": i in hits,
            })

    print({
        "rows": len(rows),
        "candidate_transition_points": len(hits),
        "min_gv_transition": round(float(np.min(gv)), 4),
        "mean_gv_transition": round(float(np.mean(gv)), 4),
        "battle": "transition_vs_magnitude",
    })


if __name__ == "__main__":
    main()
