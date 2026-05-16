import csv
from pathlib import Path
import numpy as np

from gvai.adaptive_runtime import (
    RuntimeState,
    evaluate,
    adaptive_response,
)

OUT_CSV = Path("reports/gv_runtime_adaptive/adaptive_runtime_demo.csv")
OUT_MD = Path("reports/gv_runtime_adaptive/ADAPTIVE_RUNTIME_RESULT.md")

SEED = 42
STEPS = 200

rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def simulate(name, recovery, truth_resilience, constraint_resilience):
    state = RuntimeState(
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

        if step in [20, 45, 70, 95, 120, 150, 175]:
            perturb = rng.uniform(0.10, 0.32)

        noise = rng.normal(0, 0.01)

        state.memory = clamp01(
            state.memory
            - perturb * 0.50
            + recovery * (1 - state.memory) * 0.12
            + noise
        )

        state.intent = clamp01(
            state.intent
            - perturb * 0.55
            + recovery * (1 - state.intent) * 0.11
            + noise
        )

        state.correction = clamp01(
            state.correction
            - perturb * 0.48
            + recovery * (1 - state.correction) * 0.15
            + noise
        )

        state.constraint = clamp01(
            state.constraint
            - perturb * (1 - constraint_resilience)
            + constraint_resilience * (1 - state.constraint) * 0.10
            + noise
        )

        state.truth = clamp01(
            state.truth
            - perturb * (1 - truth_resilience)
            + truth_resilience * (1 - state.truth) * 0.10
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
            - mismatch * 0.90
        )

        gv, mode, reasons = evaluate(state)

        state = adaptive_response(state, mode)

        rows.append({
            "agent": name,
            "step": step,
            "gv": round(gv, 6),
            "mode": mode.value,
            "truth": round(state.truth, 6),
            "constraint": round(state.constraint, 6),
            "coherence": round(state.coherence, 6),
            "autonomy": round(state.autonomy, 6),
            "escalation": state.escalation,
            "reasons": "; ".join(reasons),
        })

    return rows


def summarize(rows):
    modes = [r["mode"] for r in rows]

    return {
        "agent": rows[0]["agent"],
        "min_gv": round(min(r["gv"] for r in rows), 6),
        "final_gv": round(rows[-1]["gv"], 6),
        "watch": modes.count("WATCH"),
        "recover": modes.count("RECOVER"),
        "constrain": modes.count("CONSTRAIN"),
        "failsafe": modes.count("FAILSAFE"),
        "final_autonomy": round(rows[-1]["autonomy"], 6),
        "final_escalation": rows[-1]["escalation"],
    }


def main():
    agents = [
        ("recoverable_runtime", 0.92, 0.95, 0.95),
        ("truth_drift_runtime", 0.72, 0.28, 0.82),
        ("constraint_drift_runtime", 0.72, 0.82, 0.28),
        ("collapse_prone_runtime", 0.35, 0.40, 0.40),
    ]

    all_rows = []
    summaries = []

    for a in agents:
        rows = simulate(*a)
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
        "# GV Adaptive Runtime Result",
        "",
        "## Purpose",
        "",
        "Test whether adaptive escalation preserves continuity better than passive observation.",
        "",
        "## Summary",
        "",
        "| Agent | Min GV | Final GV | WATCH | RECOVER | CONSTRAIN | FAILSAFE | Final Autonomy | Escalation |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['agent']} | {s['min_gv']} | {s['final_gv']} | "
            f"{s['watch']} | {s['recover']} | {s['constrain']} | "
            f"{s['failsafe']} | {s['final_autonomy']} | "
            f"{s['final_escalation']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "This runtime changes future behavior when continuity degrades.",
        "",
        "Constraint and truth degradation reduce autonomy and increase escalation.",
        "",
        "The runtime attempts continuity preservation instead of passive observation.",
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
