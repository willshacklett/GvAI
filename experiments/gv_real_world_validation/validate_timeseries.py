import csv
import sys
from pathlib import Path
import numpy as np

BASELINE_WINDOW = 20
RECOVERY_WINDOW = 30
RETURN_TOLERANCE_RATIO = 0.10
WARNING_THRESHOLD = 0.70


def load_csv(path):
    rows = []
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    values = np.array([float(r["value"]) for r in rows], dtype=float)
    events = [r.get("event", "") for r in rows]
    return values, events


def baseline_for(values, idx):
    start = max(0, idx - BASELINE_WINDOW)
    segment = values[start:idx]
    return float(np.median(segment)) if len(segment) else float(values[0])


def recovery_time(values, idx, baseline):
    tolerance = abs(baseline) * RETURN_TOLERANCE_RATIO
    for j in range(idx + 1, min(len(values), idx + RECOVERY_WINDOW)):
        if abs(values[j] - baseline) <= tolerance:
            return j - idx
    return None


def rolling_gv(values):
    gv = np.ones(len(values))
    recovery_times = [None] * len(values)

    for idx in range(BASELINE_WINDOW, len(values)):
        baseline = baseline_for(values, idx)
        deviation = abs(values[idx] - baseline)

        if deviation < abs(baseline) * RETURN_TOLERANCE_RATIO:
            gv[idx] = gv[idx - 1]
            continue

        rt = recovery_time(values, idx, baseline)
        recovery_times[idx] = rt

        if rt is None:
            rho = 0.25
        else:
            speed = 1.0 - min(1.0, rt / RECOVERY_WINDOW)
            rho = 0.25 + 0.75 * speed

        recent = [r for r in recovery_times[max(0, idx - 100):idx + 1] if r is not None]

        if len(recent) >= 5:
            early = np.median(recent[:3])
            late = np.median(recent[-3:])
            slowing_penalty = min(1.0, max(0.0, (late - early) / RECOVERY_WINDOW))
        else:
            slowing_penalty = 0.0

        gv[idx] = max(0.0, min(1.0, rho - slowing_penalty))

    return gv, recovery_times


def first_warning(gv):
    hits = np.where(gv < WARNING_THRESHOLD)[0]
    return int(hits[0]) if len(hits) else None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate_timeseries.py data.csv")
        raise SystemExit(2)

    path = sys.argv[1]
    values, events = load_csv(path)
    gv, recovery_times = rolling_gv(values)
    warning = first_warning(gv)

    failure_indices = [
        i for i, e in enumerate(events)
        if e.lower() in {"failure", "collapse", "incident"}
    ]

    first_failure = failure_indices[0] if failure_indices else None
    lead_time = first_failure - warning if warning is not None and first_failure is not None else None

    print({
        "file": path,
        "rows": len(values),
        "first_warning": warning,
        "first_failure": first_failure,
        "lead_time": lead_time,
        "min_gv": round(float(np.min(gv)), 4),
        "mean_gv": round(float(np.mean(gv)), 4),
    })


if __name__ == "__main__":
    main()
