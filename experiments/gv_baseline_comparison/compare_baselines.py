import csv
import importlib.util
from pathlib import Path
import numpy as np

DYNAMIC_MODULE = Path("experiments/gv_falsification/dynamic_recovery_gv.py")
OUT_CSV = Path("reports/gv_baseline_comparison/baseline_comparison.csv")

SEEDS = range(1, 101)
COLLAPSE_AT = 800

GV_THRESHOLD = 0.70
Z_THRESHOLD = 3.0
ROLLING_WINDOW = 40


def load_dynamic_module():
    spec = importlib.util.spec_from_file_location("dynamic_recovery_gv", DYNAMIC_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def first_hit(values, predicate):
    for i, v in enumerate(values):
        if predicate(v):
            return i
    return None


def rolling_z_warning(signal):
    warnings = []

    for i in range(len(signal)):
        if i < ROLLING_WINDOW:
            warnings.append(False)
            continue

        window = signal[i - ROLLING_WINDOW:i]
        mean = float(np.mean(window))
        std = float(np.std(window)) or 1.0
        z = abs((signal[i] - mean) / std)
        warnings.append(z >= Z_THRESHOLD)

    return first_hit(warnings, lambda x: x is True)


def variance_warning(signal):
    rolling_vars = []

    for i in range(len(signal)):
        if i < ROLLING_WINDOW:
            rolling_vars.append(0.0)
            continue

        rolling_vars.append(float(np.var(signal[i - ROLLING_WINDOW:i])))

    baseline = np.median(rolling_vars[ROLLING_WINDOW:ROLLING_WINDOW * 2]) or 1.0

    return first_hit(rolling_vars, lambda v: v > baseline * 6.0)


def gv_warning(mod, signal):
    gv, trials, recovery_times, rho_values = mod.gv_equation(signal)
    hits = np.where(gv < GV_THRESHOLD)[0]
    return int(hits[0]) if len(hits) else None


def verdict(collapse_expected, warning):
    if collapse_expected:
        if warning is not None and warning < COLLAPSE_AT:
            return "EARLY_WARNING"
        return "MISS"

    if warning is not None:
        return "FALSE_POSITIVE"

    return "QUIET"


def main():
    mod = load_dynamic_module()
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    detectors = {
        "gv_recoverability": lambda signal: gv_warning(mod, signal),
        "rolling_z_score": rolling_z_warning,
        "rolling_variance": variance_warning,
    }

    for seed in SEEDS:
        mod.SEED = seed

        for scenario_name, maker in mod.SCENARIOS.items():
            signal, collapse_expected = maker()

            for detector_name, detector_fn in detectors.items():
                warning = detector_fn(signal)
                lead_time = COLLAPSE_AT - warning if warning is not None else None

                rows.append({
                    "seed": seed,
                    "scenario": scenario_name,
                    "detector": detector_name,
                    "collapse_expected": collapse_expected,
                    "warning": warning,
                    "lead_time": lead_time,
                    "verdict": verdict(collapse_expected, warning),
                })

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_CSV}")

    print("\nSUMMARY")
    for detector in sorted(set(r["detector"] for r in rows)):
        print(f"\nDetector: {detector}")

        for scenario in sorted(set(r["scenario"] for r in rows)):
            subset = [
                r for r in rows
                if r["detector"] == detector and r["scenario"] == scenario
            ]

            counts = {}
            leads = []

            for r in subset:
                counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
                if r["lead_time"] is not None and r["lead_time"] > 0:
                    leads.append(r["lead_time"])

            avg_lead = round(float(np.mean(leads)), 2) if leads else None

            print({
                "scenario": scenario,
                "counts": counts,
                "avg_positive_lead_time": avg_lead,
            })


if __name__ == "__main__":
    main()
