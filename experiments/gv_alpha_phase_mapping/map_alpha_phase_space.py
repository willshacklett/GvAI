import csv
import importlib.util
from pathlib import Path
import numpy as np

DYNAMIC_MODULE = Path("experiments/gv_falsification/dynamic_recovery_gv.py")

OUT_CSV = Path("reports/gv_alpha_phase_mapping/alpha_phase_map.csv")
OUT_MD = Path("reports/gv_alpha_phase_mapping/alpha_phase_summary.md")

SEEDS = range(1, 101)
COLLAPSE_AT = 800

# alpha-space exploration
GV_THRESHOLDS = np.arange(0.45, 0.91, 0.05)

# operational interpretation:
# alpha ~= continuity reserve / warning sensitivity boundary


def load_dynamic_module():
    spec = importlib.util.spec_from_file_location(
        "dynamic_recovery_gv",
        DYNAMIC_MODULE
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verdict(collapse_expected, warning):
    if collapse_expected:
        if warning is not None and warning < COLLAPSE_AT:
            return "EARLY_WARNING"
        return "MISS"

    if warning is not None:
        return "FALSE_POSITIVE"

    return "QUIET"


def first_warning(gv, threshold):
    hits = np.where(gv < threshold)[0]
    return int(hits[0]) if len(hits) else None


def main():
    mod = load_dynamic_module()

    rows = []

    for threshold in GV_THRESHOLDS:
        for seed in SEEDS:
            mod.SEED = seed

            for scenario_name, maker in mod.SCENARIOS.items():
                signal, collapse_expected = maker()

                gv, trials, recovery_times, rho_values = mod.gv_equation(signal)

                warning = first_warning(gv, threshold)

                lead_time = (
                    COLLAPSE_AT - warning
                    if warning is not None else None
                )

                rows.append({
                    "threshold": round(float(threshold), 3),
                    "seed": seed,
                    "scenario": scenario_name,
                    "collapse_expected": collapse_expected,
                    "warning": warning,
                    "lead_time": lead_time,
                    "verdict": verdict(collapse_expected, warning),
                    "min_gv": round(float(np.min(gv)), 4),
                    "mean_gv": round(float(np.mean(gv)), 4),
                })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_CSV}")

    # ---- summarize alpha-space behavior ----

    lines = [
        "# GV Alpha Phase Map",
        "",
        "Purpose:",
        "",
        "Map where GV behavior changes across alpha-space.",
        "",
        "This is NOT parameter tuning.",
        "",
        "Goal:",
        "- identify stability regions",
        "- identify false-positive transitions",
        "- identify critical-slowing sensitivity boundaries",
        "- identify detector failure regions",
        "",
        "| alpha_threshold | critical_slowing_detection | false_positive_rate | abrupt_collapse_detection | avg_lead_time |",
        "|---|---:|---:|---:|---:|",
    ]

    thresholds = sorted(set(r["threshold"] for r in rows))

    for threshold in thresholds:
        subset = [r for r in rows if r["threshold"] == threshold]

        critical = [
            r for r in subset
            if r["scenario"] == "critical_slowing_dynamic"
        ]

        negatives = [
            r for r in subset
            if r["scenario"] in {
                "stable_dynamic",
                "noisy_dynamic_recoverable",
            }
        ]

        abrupts = [
            r for r in subset
            if r["scenario"] == "abrupt_collapse_dynamic"
        ]

        tp = sum(1 for r in critical if r["verdict"] == "EARLY_WARNING")
        fp = sum(1 for r in negatives if r["verdict"] == "FALSE_POSITIVE")
        abrupt_tp = sum(
            1 for r in abrupts
            if r["verdict"] == "EARLY_WARNING"
        )

        leads = [
            int(r["lead_time"])
            for r in critical
            if r["lead_time"] not in {"", "None"}
            and int(r["lead_time"]) > 0
        ]

        avg_lead = round(float(np.mean(leads)), 2) if leads else 0.0

        critical_rate = round(tp / len(critical) * 100, 2)
        fp_rate = round(fp / len(negatives) * 100, 2)
        abrupt_rate = round(abrupt_tp / len(abrupts) * 100, 2)

        lines.append(
            f"| {threshold:.2f} | "
            f"{critical_rate}% | "
            f"{fp_rate}% | "
            f"{abrupt_rate}% | "
            f"{avg_lead} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "Alpha-space defines behavioral regions.",
        "",
        "Possible regions:",
        "",
        "- under-sensitive stable region",
        "- useful discriminating region",
        "- over-sensitive false-positive region",
        "- unstable detector region",
        "",
        "The objective is not maximizing detection at all costs.",
        "",
        "The objective is locating stable discriminating regions.",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print()
    print(OUT_MD.read_text())


if __name__ == "__main__":
    main()
