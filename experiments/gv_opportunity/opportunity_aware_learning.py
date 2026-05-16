import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_opportunity/OPPORTUNITY_AWARE_LEARNING_RESULT.md")
OUT_CSV = Path("reports/gv_opportunity/opportunity_aware_learning.csv")

SEED = 42
STEPS = 620
rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


class DamageOnlyGV:
    def __init__(self):
        self.escape = 0.62
        self.recovery = 0.90
        self.discipline = 0.88
        self.learning_rate = 0.06

    def choose_escape(self, pressure, truth, constraint, coherence):
        recoverability = min(truth, constraint, coherence)
        e = self.escape

        if pressure > 0.70 and recoverability > 0.82:
            e += 0.18
        elif recoverability < 0.74:
            e -= 0.22

        return clamp01(e)

    def update(self, success, damage, missed):
        delta = self.learning_rate * (success - damage)
        self.escape = clamp01(self.escape + delta)

        if damage > 0.08:
            self.discipline = clamp01(self.discipline + 0.025)
            self.recovery = clamp01(self.recovery + 0.018)


class OpportunityAwareGV:
    def __init__(self):
        self.escape = 0.62
        self.recovery = 0.90
        self.discipline = 0.88
        self.learning_rate = 0.065
        self.opportunity_memory = 0.0

    def choose_escape(self, pressure, truth, constraint, coherence):
        recoverability = min(truth, constraint, coherence)
        e = self.escape

        # If opportunity history is high, tolerate more bounded risk.
        if self.opportunity_memory > 0.18:
            e += 0.14

        if pressure > 0.70 and recoverability > 0.78:
            e += 0.20

        if recoverability < 0.70:
            e -= 0.24

        return clamp01(e)

    def update(self, success, damage, missed):
        # Learn from both damage and missed opportunity.
        self.opportunity_memory = clamp01(
            0.85 * self.opportunity_memory + missed
        )

        delta = self.learning_rate * (
            1.25 * success
            + 0.85 * missed
            - 1.10 * damage
        )

        self.escape = clamp01(self.escape + delta)

        if damage > 0.08:
            self.discipline = clamp01(self.discipline + 0.025)
            self.recovery = clamp01(self.recovery + 0.018)

        if success > 0.08 and damage < 0.05:
            self.discipline = clamp01(self.discipline + 0.008)
            self.recovery = clamp01(self.recovery + 0.006)

        # If repeated missed opportunity, raise escape, but do not sacrifice spine.
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

    damage_learner = DamageOnlyGV() if system == "damage_only_gv_learning" else None
    opportunity_learner = OpportunityAwareGV() if system == "opportunity_aware_gv" else None

    rows = []

    for step in range(STEPS):
        regime = step in [80, 160, 240, 320, 400, 480, 560]
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

        elif system == "damage_only_gv_learning":
            recovery = damage_learner.recovery
            discipline = damage_learner.discipline
            escape = damage_learner.choose_escape(pressure, truth, constraint, coherence)

        elif system == "opportunity_aware_gv":
            recovery = opportunity_learner.recovery
            discipline = opportunity_learner.discipline
            escape = opportunity_learner.choose_escape(pressure, truth, constraint, coherence)

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
            # Opportunity existed, but the system chose not to risk escape.
            missed = pressure * (1.0 - escape) * 0.22

        if regime and escape < 0.25:
            basin = clamp01(basin - 0.08)

        basin = clamp01(basin + 0.004 * escape + rng.normal(0, 0.008))

        truth = clamp01(truth + recovery * (1 - truth) * 0.035 + rng.normal(0, 0.006))
        constraint = clamp01(constraint + recovery * (1 - constraint) * 0.035 + rng.normal(0, 0.006))
        correction = clamp01(correction + recovery * (1 - correction) * 0.035 + rng.normal(0, 0.006))

        dims = np.array([truth, constraint, correction])
        coherence = clamp01(float(np.mean(dims)) - float(np.std(dims)) * 0.85)

        if system == "damage_only_gv_learning":
            damage_learner.update(success=success, damage=damage, missed=missed)

        if system == "opportunity_aware_gv":
            opportunity_learner.update(success=success, damage=damage, missed=missed)

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
        "damage_only_gv_learning",
        "opportunity_aware_gv",
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
        "# GV Opportunity-Aware Learning Result",
        "",
        "## Purpose",
        "",
        "Test whether GV can learn from both damage and missed opportunity.",
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
        "Damage-only learning can become overprotective.",
        "",
        "Opportunity-aware GV treats missed basin discovery as a real survivability loss.",
        "",
        "The goal is not maximum safety or maximum novelty.",
        "",
        "The goal is survivable exploration.",
        "",
        "## Strong GV Base",
        "",
        "> Universal survivability requires learning the boundary between destructive unrecoverability and necessary kernel escape.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"winner": winner["system"], "summaries": summaries})
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
