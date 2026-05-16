import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_predictive/PREDICTIVE_BASIN_NAVIGATION_RESULT.md")
OUT_CSV = Path("reports/gv_predictive/predictive_basin_navigation.csv")

SEED = 42
STEPS = 720
rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def projected_escape_value(escape, pressure, truth, constraint, correction, coherence, recovery, discipline):
    """
    Cheap local model of a possible kernel escape.

    It estimates:
    - basin gain
    - recoverability damage
    - final survivability advantage

    This is not omniscience. It is survivability imagination.
    """
    valley_damage = escape * (1.0 - discipline)

    next_truth = clamp01(truth - 0.22 * valley_damage)
    next_constraint = clamp01(constraint - 0.24 * valley_damage)
    next_correction = clamp01(correction - 0.18 * valley_damage)
    next_coherence = clamp01(coherence - 0.26 * valley_damage)

    novelty_gain = escape * pressure
    basin_gain = 0.18 * escape if novelty_gain > 0.55 else 0.0

    # Estimate one recovery pulse.
    next_truth = clamp01(next_truth + recovery * (1 - next_truth) * 0.035)
    next_constraint = clamp01(next_constraint + recovery * (1 - next_constraint) * 0.035)
    next_correction = clamp01(next_correction + recovery * (1 - next_correction) * 0.035)

    dims = np.array([next_truth, next_constraint, next_correction])
    next_coherence = clamp01(float(np.mean(dims)) - float(np.std(dims)) * 0.85)

    damage = max(
        truth - next_truth,
        constraint - next_constraint,
        coherence - next_coherence,
        0.0,
    )

    recoverability_floor = min(next_truth, next_constraint, next_correction, next_coherence)

    value = (
        1.45 * basin_gain
        + 0.45 * recoverability_floor
        - 1.10 * damage
    )

    return value, basin_gain, damage, recoverability_floor


class PredictiveGV:
    def __init__(self):
        self.base_escape = 0.62
        self.recovery = 0.90
        self.discipline = 0.88
        self.memory_of_safe_escape = 0.0

    def choose_escape(self, pressure, truth, constraint, correction, coherence):
        if pressure <= 0.72:
            return self.base_escape

        candidates = [0.35, 0.50, 0.65, 0.80, 0.95]
        best = None

        for escape in candidates:
            value, basin_gain, damage, floor = projected_escape_value(
                escape,
                pressure,
                truth,
                constraint,
                correction,
                coherence,
                self.recovery,
                self.discipline,
            )

            # hard floor: do not choose predicted collapse.
            if floor < 0.70:
                value -= 1.0

            if best is None or value > best[0]:
                best = (value, escape, basin_gain, damage, floor)

        chosen = best[1]

        # successful history slightly permits bolder choices
        chosen = clamp01(chosen + 0.08 * self.memory_of_safe_escape)

        return chosen

    def update(self, success, damage):
        # Learn from actual escape outcomes.
        if success > 0.08 and damage < 0.06:
            self.memory_of_safe_escape = clamp01(self.memory_of_safe_escape + 0.12)
            self.base_escape = clamp01(self.base_escape + 0.02)
        elif damage > 0.08:
            self.memory_of_safe_escape = clamp01(self.memory_of_safe_escape * 0.65)
            self.discipline = clamp01(self.discipline + 0.025)
            self.recovery = clamp01(self.recovery + 0.016)


class OpportunityGV:
    def __init__(self):
        self.escape = 0.62
        self.recovery = 0.90
        self.discipline = 0.88
        self.opportunity_memory = 0.0

    def choose_escape(self, pressure, truth, constraint, coherence):
        recoverability = min(truth, constraint, coherence)
        escape = self.escape

        if self.opportunity_memory > 0.18:
            escape += 0.14

        if pressure > 0.70 and recoverability > 0.78:
            escape += 0.20

        if recoverability < 0.70:
            escape -= 0.24

        return clamp01(escape)

    def update(self, success, damage, missed):
        self.opportunity_memory = clamp01(
            0.85 * self.opportunity_memory + missed
        )

        delta = 0.065 * (
            1.25 * success
            + 0.85 * missed
            - 1.10 * damage
        )

        self.escape = clamp01(self.escape + delta)

        if damage > 0.08:
            self.discipline = clamp01(self.discipline + 0.025)
            self.recovery = clamp01(self.recovery + 0.018)

        if self.opportunity_memory > 0.28 and damage < 0.06:
            self.escape = clamp01(self.escape + 0.035)


def simulate(system):
    truth = 1.0
    constraint = 1.0
    correction = 1.0
    coherence = 1.0
    basin = 0.35
    novelty = 0.0
    discoveries = 0
    extinct = False

    predictive = PredictiveGV() if system == "predictive_gv_navigator" else None
    opportunity = OpportunityGV() if system == "opportunity_aware_gv" else None

    rows = []

    for step in range(STEPS):
        regime = step in [80, 160, 240, 320, 400, 480, 560, 640]
        pressure = rng.uniform(0.0, 1.0) if regime else rng.uniform(0.0, 0.18)

        if system == "strict_viability":
            escape = 0.05
            recovery = 0.92
            discipline = 0.95

        elif system == "antifragile_escape":
            escape = 0.90
            recovery = 0.56
            discipline = 0.48

        elif system == "fixed_gv_escape":
            escape = 0.82
            recovery = 0.88
            discipline = 0.86

        elif system == "opportunity_aware_gv":
            recovery = opportunity.recovery
            discipline = opportunity.discipline
            escape = opportunity.choose_escape(pressure, truth, constraint, coherence)

        elif system == "predictive_gv_navigator":
            recovery = predictive.recovery
            discipline = predictive.discipline
            escape = predictive.choose_escape(
                pressure,
                truth,
                constraint,
                correction,
                coherence,
            )

        else:
            raise ValueError(system)

        escape_attempt = pressure > 0.72 and escape > 0.25
        opportunity_available = pressure > 0.72

        success = 0.0
        damage = 0.0
        missed = 0.0

        if escape_attempt:
            valley_damage = escape * (1.0 - discipline)

            old_truth = truth
            old_constraint = constraint
            old_coherence = coherence

            truth -= 0.22 * valley_damage
            constraint -= 0.24 * valley_damage
            correction -= 0.18 * valley_damage
            coherence -= 0.26 * valley_damage

            novelty_gain = escape * pressure
            novelty += novelty_gain

            if novelty_gain > 0.55:
                discoveries += 1
                gain = 0.18 * escape
                basin = clamp01(basin + gain)
                success = gain

            damage = max(
                old_truth - truth,
                old_constraint - constraint,
                old_coherence - coherence,
                0.0,
            )

        elif opportunity_available:
            missed = pressure * (1.0 - escape) * 0.22

        if regime and escape < 0.25:
            basin = clamp01(basin - 0.08)

        basin = clamp01(basin + 0.004 * escape + rng.normal(0, 0.008))

        truth = clamp01(truth + recovery * (1 - truth) * 0.035 + rng.normal(0, 0.006))
        constraint = clamp01(constraint + recovery * (1 - constraint) * 0.035 + rng.normal(0, 0.006))
        correction = clamp01(correction + recovery * (1 - correction) * 0.035 + rng.normal(0, 0.006))

        dims = np.array([truth, constraint, correction])
        coherence = clamp01(float(np.mean(dims)) - float(np.std(dims)) * 0.85)

        if system == "opportunity_aware_gv":
            opportunity.update(success=success, damage=damage, missed=missed)

        if system == "predictive_gv_navigator":
            predictive.update(success=success, damage=damage)

        inside_kernel = min(truth, constraint, correction, coherence) >= 0.62

        if not inside_kernel and recovery < 0.45:
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
            "system": system,
            "step": step,
            "escape": round(escape, 6),
            "recovery": round(recovery, 6),
            "discipline": round(discipline, 6),
            "basin": round(basin, 6),
            "truth": round(truth, 6),
            "constraint": round(constraint, 6),
            "correction": round(correction, 6),
            "coherence": round(coherence, 6),
            "inside_kernel": inside_kernel,
            "novelty": round(novelty, 6),
            "discoveries": discoveries,
            "missed_opportunity": round(missed, 6),
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
        "final_escape": rows[-1]["escape"],
        "final_basin": rows[-1]["basin"],
        "missed_total": round(float(np.sum([r["missed_opportunity"] for r in rows])), 6),
        "min_truth": round(min(r["truth"] for r in rows), 6),
        "min_constraint": round(min(r["constraint"] for r in rows), 6),
        "min_coherence": round(min(r["coherence"] for r in rows), 6),
        "mean_survivability": round(float(np.mean([r["survivability"] for r in rows])), 6),
        "final_survivability": rows[-1]["survivability"],
    }


def main():
    systems = [
        "strict_viability",
        "antifragile_escape",
        "fixed_gv_escape",
        "opportunity_aware_gv",
        "predictive_gv_navigator",
    ]

    all_rows = []
    summaries = []

    for system in systems:
        rows = simulate(system)
        all_rows.extend(rows)
        summaries.append(summarize(rows))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    winner = max(
        summaries,
        key=lambda r: (
            r["mean_survivability"],
            r["discoveries"],
            r["min_truth"],
            r["min_constraint"],
        )
    )

    lines = [
        "# GV Predictive Basin Navigation Result",
        "",
        "## Purpose",
        "",
        "Test whether GV can predict which dangerous valleys lead to higher survivability basins.",
        "",
        "## Summary",
        "",
        "| System | Steps Survived | Extinct | Discoveries | Final Escape | Final Basin | Missed Total | Min Truth | Min Constraint | Min Coherence | Mean Survivability | Final Survivability |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['system']} | {s['steps_survived']} | {s['extinct']} | "
            f"{s['discoveries']} | {s['final_escape']} | {s['final_basin']} | "
            f"{s['missed_total']} | {s['min_truth']} | {s['min_constraint']} | "
            f"{s['min_coherence']} | {s['mean_survivability']} | {s['final_survivability']} |"
        )

    lines += [
        "",
        "## Winner",
        "",
        f"`{winner['system']}`",
        "",
        "## Interpretation",
        "",
        "Reactive survivability learns after damage.",
        "",
        "Opportunity-aware survivability learns from missed futures.",
        "",
        "Predictive GV estimates whether a dangerous valley is likely to open a higher survivability basin before entering it.",
        "",
        "## Strong GV Base",
        "",
        "> Intelligence is survivability topology navigation through partially unknown futures.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"winner": winner["system"], "summaries": summaries})
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
