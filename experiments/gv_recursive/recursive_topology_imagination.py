import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_recursive/RECURSIVE_TOPOLOGY_IMAGINATION_RESULT.md")
OUT_CSV = Path("reports/gv_recursive/recursive_topology_imagination.csv")

SEED = 42
STEPS = 840
rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def survivability_score(
    basin,
    truth,
    constraint,
    correction,
    coherence,
    option_density,
):
    return clamp01(
        0.28 * basin
        + 0.18 * truth
        + 0.18 * constraint
        + 0.12 * correction
        + 0.12 * coherence
        + 0.12 * option_density
    )


def imagine_future(
    escape,
    pressure,
    truth,
    constraint,
    correction,
    coherence,
    recovery,
    discipline,
    option_density,
    depth=3,
):
    """
    Recursive survivability imagination.

    The system estimates:
    - future basin accessibility
    - future option-space density
    - future recoverability
    - future navigability

    across recursively imagined trajectories.
    """

    valley_damage = escape * (1.0 - discipline)

    truth2 = clamp01(truth - 0.20 * valley_damage)
    constraint2 = clamp01(constraint - 0.22 * valley_damage)
    correction2 = clamp01(correction - 0.16 * valley_damage)
    coherence2 = clamp01(coherence - 0.24 * valley_damage)

    novelty_gain = escape * pressure

    basin2 = 0.0
    if novelty_gain > 0.55:
        basin2 = 0.18 * escape

    # Successful exploration increases future option-space.
    option2 = clamp01(
        option_density
        + 0.12 * basin2
        - 0.10 * valley_damage
    )

    truth2 = clamp01(truth2 + recovery * (1 - truth2) * 0.03)
    constraint2 = clamp01(constraint2 + recovery * (1 - constraint2) * 0.03)
    correction2 = clamp01(correction2 + recovery * (1 - correction2) * 0.03)

    dims = np.array([truth2, constraint2, correction2])
    coherence2 = clamp01(
        float(np.mean(dims)) - float(np.std(dims)) * 0.82
    )

    local_score = survivability_score(
        basin2,
        truth2,
        constraint2,
        correction2,
        coherence2,
        option2,
    )

    if depth <= 1:
        return local_score

    future_pressures = [0.35, 0.55, 0.80]

    recursive_scores = []

    for p in future_pressures:
        future_escape = clamp01(
            0.72 * escape + 0.18 * option2
        )

        s = imagine_future(
            future_escape,
            p,
            truth2,
            constraint2,
            correction2,
            coherence2,
            recovery,
            discipline,
            option2,
            depth=depth - 1,
        )

        recursive_scores.append(s)

    return clamp01(
        0.45 * local_score
        + 0.55 * float(np.mean(recursive_scores))
    )


class RecursiveGV:
    def __init__(self):
        self.base_escape = 0.62
        self.recovery = 0.90
        self.discipline = 0.88
        self.option_density = 0.50

    def choose_escape(
        self,
        pressure,
        truth,
        constraint,
        correction,
        coherence,
    ):
        candidates = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95]

        best = None

        for escape in candidates:
            imagined = imagine_future(
                escape,
                pressure,
                truth,
                constraint,
                correction,
                coherence,
                self.recovery,
                self.discipline,
                self.option_density,
                depth=3,
            )

            floor = min(
                truth,
                constraint,
                correction,
                coherence,
            )

            if floor < 0.68:
                imagined -= 0.4

            if best is None or imagined > best[0]:
                best = (imagined, escape)

        return best[1]

    def update(self, success, damage):
        if success > 0.08 and damage < 0.05:
            self.option_density = clamp01(
                self.option_density + 0.035
            )
            self.base_escape = clamp01(
                self.base_escape + 0.015
            )

        if damage > 0.08:
            self.option_density = clamp01(
                self.option_density - 0.05
            )
            self.discipline = clamp01(
                self.discipline + 0.02
            )
            self.recovery = clamp01(
                self.recovery + 0.015
            )


def simulate(system):
    truth = 1.0
    constraint = 1.0
    correction = 1.0
    coherence = 1.0
    basin = 0.35
    novelty = 0.0
    discoveries = 0
    extinct = False
    option_density = 0.50

    recursive = RecursiveGV() if system == "recursive_gv" else None

    rows = []

    for step in range(STEPS):
        regime = step in [80,160,240,320,400,480,560,640,720]
        pressure = rng.uniform(0.0, 1.0) if regime else rng.uniform(0.0, 0.18)

        if system == "antifragile_escape":
            escape = 0.90
            recovery = 0.56
            discipline = 0.48

        elif system == "fixed_gv_escape":
            escape = 0.82
            recovery = 0.88
            discipline = 0.86

        elif system == "predictive_gv":
            escape = 0.66
            recovery = 0.90
            discipline = 0.88

        elif system == "recursive_gv":
            recovery = recursive.recovery
            discipline = recursive.discipline
            escape = recursive.choose_escape(
                pressure,
                truth,
                constraint,
                correction,
                coherence,
            )
            option_density = recursive.option_density

        else:
            raise ValueError(system)

        escape_attempt = pressure > 0.72 and escape > 0.25

        success = 0.0
        damage = 0.0

        if escape_attempt:
            valley_damage = escape * (1.0 - discipline)

            old_truth = truth
            old_constraint = constraint
            old_coherence = coherence

            truth -= 0.20 * valley_damage
            constraint -= 0.22 * valley_damage
            correction -= 0.16 * valley_damage
            coherence -= 0.24 * valley_damage

            novelty_gain = escape * pressure
            novelty += novelty_gain

            if novelty_gain > 0.55:
                discoveries += 1
                gain = 0.18 * escape
                basin = clamp01(basin + gain)
                success = gain

                option_density = clamp01(
                    option_density + 0.025
                )

            damage = max(
                old_truth - truth,
                old_constraint - constraint,
                old_coherence - coherence,
                0.0,
            )

        basin = clamp01(
            basin + 0.004 * escape + rng.normal(0, 0.008)
        )

        truth = clamp01(
            truth + recovery * (1 - truth) * 0.035 + rng.normal(0, 0.006)
        )

        constraint = clamp01(
            constraint + recovery * (1 - constraint) * 0.035 + rng.normal(0, 0.006)
        )

        correction = clamp01(
            correction + recovery * (1 - correction) * 0.035 + rng.normal(0, 0.006)
        )

        dims = np.array([truth, constraint, correction])

        coherence = clamp01(
            float(np.mean(dims)) - float(np.std(dims)) * 0.82
        )

        if system == "recursive_gv":
            recursive.update(success, damage)

        survivability = survivability_score(
            basin,
            truth,
            constraint,
            correction,
            coherence,
            option_density,
        )

        rows.append({
            "system": system,
            "step": step,
            "escape": round(escape, 6),
            "basin": round(basin, 6),
            "truth": round(truth, 6),
            "constraint": round(constraint, 6),
            "coherence": round(coherence, 6),
            "option_density": round(option_density, 6),
            "discoveries": discoveries,
            "survivability": round(survivability, 6),
        })

    return rows


def summarize(rows):
    return {
        "system": rows[0]["system"],
        "discoveries": rows[-1]["discoveries"],
        "final_escape": rows[-1]["escape"],
        "final_option_density": rows[-1]["option_density"],
        "min_truth": round(min(r["truth"] for r in rows), 6),
        "min_constraint": round(min(r["constraint"] for r in rows), 6),
        "min_coherence": round(min(r["coherence"] for r in rows), 6),
        "mean_survivability": round(
            float(np.mean([r["survivability"] for r in rows])),
            6,
        ),
        "final_survivability": rows[-1]["survivability"],
    }


def main():
    systems = [
        "antifragile_escape",
        "fixed_gv_escape",
        "predictive_gv",
        "recursive_gv",
    ]

    all_rows = []
    summaries = []

    for system in systems:
        rows = simulate(system)
        all_rows.extend(rows)
        summaries.append(summarize(rows))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(all_rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(all_rows)

    winner = max(
        summaries,
        key=lambda r: (
            r["mean_survivability"],
            r["discoveries"],
            r["final_option_density"],
        )
    )

    lines = [
        "# GV Recursive Topology Imagination Result",
        "",
        "## Purpose",
        "",
        "Test recursive survivability topology imagination.",
        "",
        "## Summary",
        "",
        "| System | Discoveries | Final Escape | Final Option Density | Min Truth | Min Constraint | Min Coherence | Mean Survivability | Final Survivability |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['system']} | {s['discoveries']} | "
            f"{s['final_escape']} | {s['final_option_density']} | "
            f"{s['min_truth']} | {s['min_constraint']} | "
            f"{s['min_coherence']} | {s['mean_survivability']} | "
            f"{s['final_survivability']} |"
        )

    lines += [
        "",
        "## Winner",
        "",
        f"`{winner['system']}`",
        "",
        "## Interpretation",
        "",
        "Recursive GV does not merely predict immediate survivability.",
        "",
        "It recursively estimates future navigability and option-space preservation.",
        "",
        "The target is no longer safety or reward.",
        "",
        "The target becomes future survivability accessibility itself.",
        "",
        "## Strongest GV Base",
        "",
        "> Intelligence may fundamentally be recursive survivability topology imagination.",
    ]

    OUT_MD.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print({
        "winner": winner["system"],
        "summaries": summaries,
    })

    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
