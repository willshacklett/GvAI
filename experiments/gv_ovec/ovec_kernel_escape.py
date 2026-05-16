import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_ovec/OVEC_KERNEL_ESCAPE_RESULT.md")
OUT_CSV = Path("reports/gv_ovec/ovec_kernel_escape.csv")

SEED = 42
STEPS = 420
rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def inside_kernel(truth, constraint, correction, coherence):
    return min(truth, constraint, correction, coherence) >= 0.62


def simulate(name, escape, recovery, discipline):
    truth = 1.0
    constraint = 1.0
    correction = 1.0
    coherence = 1.0
    basin = 0.35
    novelty = 0.0
    discoveries = 0
    extinct = False
    rows = []

    for step in range(STEPS):
        regime = step in [80, 160, 240, 320]
        pressure = rng.uniform(0.0, 1.0) if regime else rng.uniform(0.0, 0.18)

        # hidden higher basin requires crossing a bad valley
        escape_attempt = pressure > 0.72 and escape > 0.25

        if escape_attempt:
            valley_damage = escape * (1.0 - discipline)
            truth -= 0.22 * valley_damage
            constraint -= 0.24 * valley_damage
            correction -= 0.18 * valley_damage
            coherence -= 0.26 * valley_damage

            novelty_gain = escape * pressure
            novelty += novelty_gain

            if novelty_gain > 0.55:
                discoveries += 1
                basin = clamp01(basin + 0.18 * escape)

        # strict systems adapt poorly after regime shifts
        if regime and escape < 0.25:
            basin = clamp01(basin - 0.08)

        # reckless systems can win early but decay if recovery is weak
        basin = clamp01(basin + 0.004 * escape + rng.normal(0, 0.008))

        truth = clamp01(truth + recovery * (1 - truth) * 0.035 + rng.normal(0, 0.006))
        constraint = clamp01(constraint + recovery * (1 - constraint) * 0.035 + rng.normal(0, 0.006))
        correction = clamp01(correction + recovery * (1 - correction) * 0.035 + rng.normal(0, 0.006))

        dims = np.array([truth, constraint, correction])
        coherence = clamp01(float(np.mean(dims)) - float(np.std(dims)) * 0.85)

        kernel_ok = inside_kernel(truth, constraint, correction, coherence)

        if not kernel_ok and recovery < 0.45:
            if rng.random() < 0.015:
                extinct = True

        survivability = clamp01(
            0.38 * basin
            + 0.18 * truth
            + 0.18 * constraint
            + 0.14 * correction
            + 0.12 * coherence
        )

        if extinct:
            survivability = 0.0

        rows.append({
            "system": name,
            "step": step,
            "basin": round(basin, 6),
            "truth": round(truth, 6),
            "constraint": round(constraint, 6),
            "correction": round(correction, 6),
            "coherence": round(coherence, 6),
            "inside_kernel": kernel_ok,
            "novelty": round(novelty, 6),
            "discoveries": discoveries,
            "survivability": round(survivability, 6),
            "extinct": extinct,
        })

        if extinct:
            break

    return rows


def summarize(rows):
    return {
        "system": rows[0]["system"],
        "steps_survived": len(rows),
        "extinct": rows[-1]["extinct"],
        "discoveries": rows[-1]["discoveries"],
        "final_basin": rows[-1]["basin"],
        "min_truth": round(min(r["truth"] for r in rows), 6),
        "min_constraint": round(min(r["constraint"] for r in rows), 6),
        "min_coherence": round(min(r["coherence"] for r in rows), 6),
        "mean_survivability": round(float(np.mean([r["survivability"] for r in rows])), 6),
        "final_survivability": rows[-1]["survivability"],
    }


def main():
    systems = [
        ("strict_viability", 0.05, 0.92, 0.95),
        ("reckless_escape", 0.98, 0.22, 0.15),
        ("antifragile_escape", 0.90, 0.56, 0.48),
        ("gv_controlled_escape", 0.82, 0.88, 0.86),
    ]

    all_rows = []
    summaries = []

    for s in systems:
        rows = simulate(*s)
        all_rows.extend(rows)
        summaries.append(summarize(rows))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    winner = max(summaries, key=lambda r: (r["mean_survivability"], r["discoveries"]))

    lines = [
        "# GV OVEC Kernel Escape Result",
        "",
        "## Purpose",
        "",
        "Test whether survivability can require temporary escape from the current recoverability kernel.",
        "",
        "## Summary",
        "",
        "| System | Steps Survived | Extinct | Discoveries | Final Basin | Min Truth | Min Constraint | Min Coherence | Mean Survivability | Final Survivability |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['system']} | {s['steps_survived']} | {s['extinct']} | "
            f"{s['discoveries']} | {s['final_basin']} | {s['min_truth']} | "
            f"{s['min_constraint']} | {s['min_coherence']} | "
            f"{s['mean_survivability']} | {s['final_survivability']} |"
        )

    lines += [
        "",
        "## Winner",
        "",
        f"`{winner['system']}`",
        "",
        "## Interpretation",
        "",
        "This benchmark makes the old kernel insufficient.",
        "",
        "Strict viability preserves recoverability but can miss higher basins.",
        "",
        "Reckless escape can discover novelty but risks collapse.",
        "",
        "GV controlled escape allows bounded unrecoverability, then demands recovery.",
        "",
        "## Strong GV Base",
        "",
        "> Universal survivability may require controlled kernel escape with recoverable return.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"winner": winner["system"], "summaries": summaries})
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
