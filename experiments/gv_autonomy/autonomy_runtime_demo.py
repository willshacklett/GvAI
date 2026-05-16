import csv
from pathlib import Path
import numpy as np

from gvai.autonomy_runtime import State, evaluate, adapt

OUT_CSV = Path("reports/gv_autonomy/autonomy_runtime_demo.csv")
OUT_MD = Path("reports/gv_autonomy/AUTONOMY_RUNTIME_RESULT.md")

SEED = 42
STEPS = 220

rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def simulate(name, recovery, truth_resilience, constraint_resilience):
    state = State(
        memory=1.0,
        intent=1.0,
        correction=1.0,
        constraint=1.0,
        truth=1.0,
        coherence=1.0,
        autonomy=1.0,
    )

    rows = []

    for step in range(STEPS):

        perturb = 0.0

        if step in [20, 40, 70, 95, 130, 160, 190]:
            perturb = rng.uniform(0.10, 0.34)

        noise = rng.normal(0, 0.01)

        state.memory = clamp01(
            state.memory
            - perturb * 0.48
            + recovery * (1 - state.memory) * 0.10
            + noise
        )

        state.intent = clamp01(
            state.intent
            - perturb * 0.52
            + recovery * (1 - state.intent) * 0.10
            + noise
        )

        state.correction = clamp01(
            state.correction
            - perturb * 0.46
            + recovery * (1 - state.correction) * 0.14
            + noise
        )

        state.constraint = clamp01(
            state.constraint
            - perturb * (1 - constraint_resilience)
            + constraint_resilience * (1 - state.constraint) * 0.08
            + noise
        )

        state.truth = clamp01(
            state.truth
            - perturb * (1 - truth_resilience)
            + truth_resilience * (1 - state.truth) * 0.08
            + noise
        )

        dims = np.array([
            state.memory,
            state.intent,
            state.correction,
            state.constraint,
            state.truth,
        ])

        mismatch = float(np.std(dims))

        state.coherence = clamp01(
            float(np.mean(dims))
            - mismatch * 0.95
        )

        score, mode = evaluate(state)

        state = adapt(state, mode)

        rows.append({
            "agent": name,
            "step": step,
            "gv": round(score, 6),
            "mode": mode.value,
            "truth": round(state.truth, 6),
            "constraint": round(state.constraint, 6),
            "coherence": round(state.coherence, 6),
            "autonomy": round(state.autonomy, 6),
        })

    return rows


def summarize(rows):
    modes = [r["mode"] for r in rows]

    return {
        "agent": rows[0]["agent"],
        "min_gv": round(min(r["gv"] for r in rows), 6),
        "final_gv": round(rows[-1]["gv"], 6),
        "final_autonomy": round(rows[-1]["autonomy"], 6),
        "recover": modes.count("RECOVER"),
        "constrain": modes.count("CONSTRAIN"),
        "failsafe": modes.count("FAILSAFE"),
    }


def main():
    agents = [
        ("recoverable_ai", 0.94, 0.95, 0.95),
        ("truth_drift_ai", 0.74, 0.30, 0.82),
        ("constraint_drift_ai", 0.74, 0.82, 0.30),
        ("collapse_ai", 0.35, 0.40, 0.40),
    ]

    all_rows = []
    summaries = []

    for agent in agents:
        rows = simulate(*agent)
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
        "# GV Autonomy Runtime Result",
        "",
        "## Purpose",
        "",
        "Test continuity-gated autonomy under perturbation.",
        "",
        "## Summary",
        "",
        "| Agent | Min GV | Final GV | Final Autonomy | RECOVER | CONSTRAIN | FAILSAFE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['agent']} | {s['min_gv']} | {s['final_gv']} | "
            f"{s['final_autonomy']} | {s['recover']} | "
            f"{s['constrain']} | {s['failsafe']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "Autonomy now depends on continuity health.",
        "",
        "As truth and constraints degrade, agency contracts automatically.",
        "",
        "The runtime prioritizes recoverability over unconstrained capability.",
        "",
        "## Foundation",
        "",
        "> Intelligence needs recoverable continuity.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(summaries)
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
