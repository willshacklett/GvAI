import csv
import importlib.util
from pathlib import Path
import numpy as np

MODULE_PATH = Path("experiments/gv_falsification/dynamic_recovery_gv.py")
OUT_DIR = Path("data/gv_falsification")
OUT_CSV = OUT_DIR / "dynamic_seed_sweep.csv"

SEEDS = range(1, 101)
THRESHOLDS = [0.55, 0.60, 0.65, 0.70]
COLLAPSE_AT = 800


def load_module():
    spec = importlib.util.spec_from_file_location("dynamic_recovery_gv", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def first_warning(gv, threshold):
    hits = np.where(gv < threshold)[0]
    return int(hits[0]) if len(hits) else None


def doubled_recovery_warning(recovery_times):
    """
    Mechanism rule:

    Do not warn on one temporary slowdown.

    Warn only when both are true:

    1. recovery time doubles in 2 out of the last 3 trials
    2. recent median recovery is worse than earlier median recovery

    This tries to separate temporary noise from directional loss of recoverability.
    """

    valid = [r for r in recovery_times if r is not None]

    if len(valid) < 8:
        return None

    baseline = float(np.median(valid[:5]))

    doubled_flags = []

    for idx, rt in enumerate(recovery_times):
        if rt is None:
            doubled_flags.append(True)
        else:
            doubled_flags.append(rt >= baseline * 2.0)

        if idx < 7:
            continue

        recent_flags = doubled_flags[idx - 2:idx + 1]
        persistence_hit = sum(recent_flags) >= 2

        earlier_window = [
            r for r in recovery_times[max(0, idx - 8):max(0, idx - 3)]
            if r is not None
        ]

        recent_window = [
            r for r in recovery_times[max(0, idx - 2):idx + 1]
            if r is not None
        ]

        if len(earlier_window) < 3 or len(recent_window) < 2:
            continue

        earlier_median = float(np.median(earlier_window))
        recent_median = float(np.median(recent_window))

        directional_degradation = recent_median > earlier_median * 1.35

        if persistence_hit and directional_degradation:
            return idx

    return None


def verdict_for(collapse_expected, warning):
    if collapse_expected:
        if warning is not None and warning < COLLAPSE_AT:
            return "PASS_EARLY_WARNING"
        return "MISS"
    else:
        if warning is not None:
            return "FALSE_POSITIVE"
        return "PASS_QUIET"


def main():
    mod = load_module()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []

    for seed in SEEDS:
        mod.SEED = seed

        for scenario_name, maker in mod.SCENARIOS.items():
            signal, collapse_expected = maker()
            gv, trials, recovery_times, rho_values = mod.gv_equation(signal)

            doubled_warning_idx = doubled_recovery_warning(recovery_times)

            for threshold in THRESHOLDS:
                gv_warning = first_warning(gv, threshold)

                recovery_warning = None
                if doubled_warning_idx is not None:
                    recovery_warning = trials[doubled_warning_idx]

                combined_warning_candidates = [
                    w for w in [gv_warning, recovery_warning]
                    if w is not None
                ]

                combined_warning = (
                    min(combined_warning_candidates)
                    if combined_warning_candidates else None
                )

                lead_time = (
                    COLLAPSE_AT - combined_warning
                    if combined_warning is not None else None
                )

                verdict = verdict_for(collapse_expected, combined_warning)

                rows.append({
                    "seed": seed,
                    "scenario": scenario_name,
                    "threshold": threshold,
                    "gv_warning": gv_warning,
                    "recovery_warning": recovery_warning,
                    "combined_warning": combined_warning,
                    "collapse_expected": collapse_expected,
                    "lead_time": lead_time,
                    "verdict": verdict,
                    "min_gv": round(float(np.nanmin(gv)), 4),
                    "mean_gv": round(float(np.nanmean(gv)), 4),
                    "mean_rho": round(float(np.nanmean(rho_values)), 4),
                    "failed_recoveries": int(sum(1 for r in recovery_times if r is None)),
                    "trial_count": len(trials),
                })

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_CSV}")

    print("\nSUMMARY BY SCENARIO + THRESHOLD")
    for scenario in sorted(set(r["scenario"] for r in rows)):
        for threshold in THRESHOLDS:
            subset = [r for r in rows if r["scenario"] == scenario and r["threshold"] == threshold]
            counts = {}
            lead_times = []

            for r in subset:
                counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
                if r["lead_time"] is not None and r["lead_time"] > 0:
                    lead_times.append(r["lead_time"])

            avg_lead = round(float(np.mean(lead_times)), 2) if lead_times else None
            print({
                "scenario": scenario,
                "threshold": threshold,
                "counts": counts,
                "avg_positive_lead_time": avg_lead,
            })


if __name__ == "__main__":
    main()
