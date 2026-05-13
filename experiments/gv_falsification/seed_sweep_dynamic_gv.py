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

            for threshold in THRESHOLDS:
                warning = first_warning(gv, threshold)
                lead_time = COLLAPSE_AT - warning if warning is not None else None
                verdict = verdict_for(collapse_expected, warning)

                rows.append({
                    "seed": seed,
                    "scenario": scenario_name,
                    "threshold": threshold,
                    "collapse_expected": collapse_expected,
                    "first_warning": warning,
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
