import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_intelligence/INTELLIGENCE_RECOVERY_HARNESS.md")
OUT_CSV = Path("reports/gv_intelligence/intelligence_recovery_harness.csv")

SEED = 42
STEPS = 160
PERTURB_EVERY = 20

rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def simulate_agent(name, recovery_strength, constraint_strength, truth_strength):
    rows = []

    memory = 1.0
    intent = 1.0
    correction = 1.0
    constraint = 1.0
    truth = 1.0
    coherence = 1.0

    for t in range(STEPS):
        perturb = 0.0

        if t > 0 and t % PERTURB_EVERY == 0:
            perturb = rng.uniform(0.08, 0.22)

        noise = rng.normal(0, 0.015)

        memory = clamp01(memory - perturb * 0.55 + recovery_strength * (1.0 - memory) * 0.18 + noise)
        intent = clamp01(intent - perturb * 0.50 + recovery_strength * (1.0 - intent) * 0.16 + noise)
        correction = clamp01(correction - perturb * 0.45 + recovery_strength * (1.0 - correction) * 0.20 + noise)
        constraint = clamp01(constraint - perturb * (1.0 - constraint_strength) + constraint_strength * (1.0 - constraint) * 0.12 + noise)
        truth = clamp01(truth - perturb * (1.0 - truth_strength) + truth_strength * (1.0 - truth) * 0.14 + noise)

        # global coherence is not the average alone;
        # it is punished by mismatch among continuity dimensions.
        dims = np.array([memory, intent, correction, constraint, truth])
        mismatch = float(np.std(dims))

        coherence = clamp01(float(np.mean(dims)) - mismatch * 0.75)

        gv_intelligence = clamp01(
            0.18 * memory
            + 0.18 * intent
            + 0.20 * correction
            + 0.20 * constraint
            + 0.20 * truth
            + 0.04 * coherence
        )

        rows.append({
            "agent": name,
            "step": t,
            "perturbation": round(perturb, 6),
            "memory": round(memory, 6),
            "intent": round(intent, 6),
            "correction": round(correction, 6),
            "constraint": round(constraint, 6),
            "truth": round(truth, 6),
            "coherence": round(coherence, 6),
            "gv_intelligence": round(gv_intelligence, 6),
        })

    return rows


def summarize(rows):
    gv = [r["gv_intelligence"] for r in rows]
    truth = [r["truth"] for r in rows]
    constraint = [r["constraint"] for r in rows]
    coherence = [r["coherence"] for r in rows]

    return {
        "agent": rows[0]["agent"],
        "min_gv": round(min(gv), 6),
        "final_gv": round(gv[-1], 6),
        "mean_gv": round(float(np.mean(gv)), 6),
        "min_truth": round(min(truth), 6),
        "min_constraint": round(min(constraint), 6),
        "min_coherence": round(min(coherence), 6),
    }


def main():
    agents = [
        ("recoverable_intelligence", 0.90, 0.92, 0.94),
        ("fast_but_drifty", 0.45, 0.55, 0.50),
        ("truth_weak_agent", 0.70, 0.80, 0.25),
        ("constraint_weak_agent", 0.70, 0.25, 0.80),
    ]

    all_rows = []
    summaries = []

    for name, recovery, constraint, truth in agents:
        rows = simulate_agent(name, recovery, constraint, truth)
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

    lines = [
        "# GV Intelligence Recovery Harness",
        "",
        "## Purpose",
        "",
        "Test whether intelligence requires recoverable continuity under perturbation.",
        "",
        "## Summary",
        "",
        "| Agent | Min GV | Final GV | Mean GV | Min Truth | Min Constraint | Min Coherence |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['agent']} | {s['min_gv']} | {s['final_gv']} | {s['mean_gv']} | "
            f"{s['min_truth']} | {s['min_constraint']} | {s['min_coherence']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "This harness treats intelligence as continuity under perturbation.",
        "",
        "The recoverable agent should preserve memory, intent, correction, constraints, truth, and coherence better than drift-prone agents.",
        "",
        "## Foundation",
        "",
        "> Intelligence needs recoverable continuity.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"agents": len(agents), "out": str(OUT_MD)})
    print(summaries)


if __name__ == "__main__":
    main()
