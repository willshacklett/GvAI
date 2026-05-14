import csv
from pathlib import Path
from collections import defaultdict

IN_CSV = Path("reports/gv_baseline_comparison/baseline_comparison.csv")
OUT_MD = Path("reports/gv_baseline_comparison/baseline_scorecard.md")

POSITIVE_SCENARIOS = {"critical_slowing_dynamic"}
NEGATIVE_SCENARIOS = {"stable_dynamic", "noisy_dynamic_recoverable"}
ABRUPT_SCENARIOS = {"abrupt_collapse_dynamic"}


def load_rows():
    with IN_CSV.open(newline="") as f:
        return list(csv.DictReader(f))


def pct(n, d):
    return round((n / d) * 100, 2) if d else 0.0


def main():
    rows = load_rows()
    detectors = sorted(set(r["detector"] for r in rows))

    lines = [
        "# GV Baseline Scorecard",
        "",
        "Purpose: compare GV against simpler detectors without protecting GV.",
        "",
        "| Detector | True Positive Rate | False Positive Rate | Abrupt Miss Rate | Avg Lead Time |",
        "|---|---:|---:|---:|---:|",
    ]

    for detector in detectors:
        subset = [r for r in rows if r["detector"] == detector]

        positives = [r for r in subset if r["scenario"] in POSITIVE_SCENARIOS]
        negatives = [r for r in subset if r["scenario"] in NEGATIVE_SCENARIOS]
        abrupts = [r for r in subset if r["scenario"] in ABRUPT_SCENARIOS]

        tp = sum(1 for r in positives if r["verdict"] == "EARLY_WARNING")
        fp = sum(1 for r in negatives if r["verdict"] == "FALSE_POSITIVE")
        abrupt_miss = sum(1 for r in abrupts if r["verdict"] == "MISS")

        leads = [
            int(r["lead_time"])
            for r in positives
            if r["lead_time"] not in {"", "None"} and int(r["lead_time"]) > 0
        ]

        avg_lead = round(sum(leads) / len(leads), 2) if leads else 0.0

        lines.append(
            f"| {detector} | {pct(tp, len(positives))}% | {pct(fp, len(negatives))}% | {pct(abrupt_miss, len(abrupts))}% | {avg_lead} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "- Rolling variance is too sensitive and false-alarms on stable/noisy recoverable systems.",
        "- Rolling z-score is quiet but misses critical slowing.",
        "- GV currently occupies the useful middle: low false positives with partial critical-slowing sensitivity.",
        "",
        "## Current honest limitation",
        "",
        "GV is not yet sensitive enough. It must improve critical-slowing detection without increasing false positives.",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(OUT_MD.read_text())


if __name__ == "__main__":
    main()
