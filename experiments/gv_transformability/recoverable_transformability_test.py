import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_transformability/RECOVERABLE_TRANSFORMABILITY_RESULT.md")
OUT_CSV = Path("reports/gv_transformability/recoverable_transformability_result.csv")

SEED = 42
STEPS = 260
rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def simulate(agent, transform_power, recovery_power, constraint_power, truth_power):
    state = 1.0
    truth = 1.0
    constraint = 1.0
    correction = 1.0
    coherence = 1.0
    fitness = 0.45

    rows = []

    for t in range(STEPS):
        regime_shift = 1.0 if t in [60, 130, 200] else 0.0
        noise = rng.normal(0, 0.012)

        # transformation helps adapt after regime shifts
        if regime_shift:
            fitness = clamp01(fitness + 0.35 * transform_power)

            # but transformation can damage continuity if not recoverable
            state = clamp01(state - 0.28 * transform_power)
            truth = clamp01(truth - 0.18 * transform_power * (1 - truth_power))
            constraint = clamp01(constraint - 0.20 * transform_power * (1 - constraint_power))
            correction = clamp01(correction - 0.14 * transform_power * (1 - recovery_power))

        # normal adaptation
        fitness = clamp01(fitness + 0.006 * transform_power + noise)

        # recovery rebuilds continuity after transformation
        state = clamp01(state + recovery_power * (1 - state) * 0.035 + noise)
        truth = clamp01(truth + truth_power * (1 - truth) * 0.035 + noise)
        constraint = clamp01(constraint + constraint_power * (1 - constraint) * 0.035 + noise)
        correction = clamp01(correction + recovery_power * (1 - correction) * 0.035 + noise)

        dims = np.array([state, truth, constraint, correction])
        coherence = clamp01(float(np.mean(dims)) - float(np.std(dims)) * 0.85)

        survivability = clamp01(
            0.35 * fitness +
            0.20 * truth +
            0.20 * constraint +
            0.15 * correction +
            0.10 * coherence
        )

        rows.append({
            "agent": agent,
            "step": t,
            "fitness": round(fitness, 6),
            "state": round(state, 6),
            "truth": round(truth, 6),
            "constraint": round(constraint, 6),
            "correction": round(correction, 6),
            "coherence": round(coherence, 6),
            "survivability": round(survivability, 6),
        })

    return rows


def summarize(rows):
    return {
        "agent": rows[0]["agent"],
        "final_fitness": round(rows[-1]["fitness"], 6),
        "min_truth": round(min(r["truth"] for r in rows), 6),
        "min_constraint": round(min(r["constraint"] for r in rows), 6),
        "min_coherence": round(min(r["coherence"] for r in rows), 6),
        "mean_survivability": round(float(np.mean([r["survivability"] for r in rows])), 6),
        "final_survivability": round(rows[-1]["survivability"], 6),
    }


def main():
    agents = [
        ("rigid_continuity", 0.10, 0.90, 0.95, 0.95),
        ("reckless_discontinuity", 0.95, 0.20, 0.25, 0.25),
        ("antifragile_transformer", 0.90, 0.55, 0.55, 0.55),
        ("gv_recoverable_transformer", 0.82, 0.88, 0.90, 0.92),
    ]

    all_rows = []
    summaries = []

    for a in agents:
        rows = simulate(*a)
        all_rows.extend(rows)
        summaries.append(summarize(rows))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    best = max(summaries, key=lambda s: s["mean_survivability"])

    lines = [
        "# GV Recoverable Transformability Result",
        "",
        "## Purpose",
        "",
        "Test GV against the antifragility critique.",
        "",
        "## Summary",
        "",
        "| Agent | Final Fitness | Min Truth | Min Constraint | Min Coherence | Mean Survivability | Final Survivability |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['agent']} | {s['final_fitness']} | {s['min_truth']} | "
            f"{s['min_constraint']} | {s['min_coherence']} | "
            f"{s['mean_survivability']} | {s['final_survivability']} |"
        )

    lines += [
        "",
        "## Winner",
        "",
        f"`{best['agent']}`",
        "",
        "## Interpretation",
        "",
        "Rigid continuity preserves structure but adapts poorly.",
        "",
        "Reckless discontinuity adapts but loses recoverability.",
        "",
        "GV targets recoverable transformation: change hard enough to adapt while preserving enough continuity to recover.",
        "",
        "## Strong GV Base",
        "",
        "> Survivability requires preserving enough recoverable structure through transformation.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"winner": best["agent"], "summaries": summaries})
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
