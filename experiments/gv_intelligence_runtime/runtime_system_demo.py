import csv
from pathlib import Path
import numpy as np

from gvai.intelligence_runtime import IntelligenceState, evaluate_runtime

OUT_CSV = Path("reports/gv_intelligence_runtime/runtime_system_demo.csv")
OUT_MD = Path("reports/gv_intelligence_runtime/RUNTIME_SYSTEM_RESULT.md")

SEED = 42
STEPS = 180

rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def run_agent(name, recovery, truth_resilience, constraint_resilience):
    memory = 1.0
    intent = 1.0
    correction = 1.0
    constraint = 1.0
    truth = 1.0
    coherence = 1.0

    rows = []

    for step in range(STEPS):
        perturb = 0.0

        if step in [25, 55, 90, 125, 150]:
            perturb = rng.uniform(0.10, 0.28)

        # degradation pressure
        memory = clamp01(memory - perturb * 0.45 + recovery * (1 - memory) * 0.16 + rng.normal(0, 0.01))
        intent = clamp01(intent - perturb * 0.50 + recovery * (1 - intent) * 0.15 + rng.normal(0, 0.01))
        correction = clamp01(correction - perturb * 0.42 + recovery * (1 - correction) * 0.20 + rng.normal(0, 0.01))
        constraint = clamp01(constraint - perturb * (1 - constraint_resilience) + constraint_resilience * (1 - constraint) * 0.14 + rng.normal(0, 0.01))
        truth = clamp01(truth - perturb * (1 - truth_resilience) + truth_resilience * (1 - truth) * 0.14 + rng.normal(0, 0.01))

        dims = np.array([memory, intent, correction, constraint, truth])
        coherence = clamp01(float(np.mean(dims)) - float(np.std(dims)) * 0.85)

        state = IntelligenceState(
            memory=memory,
            intent=intent,
            correction=correction,
            constraint=constraint,
            truth=truth,
            coherence=coherence,
        )

        decision = evaluate_runtime(state)

        # Runtime recovery actions actually feed back into system.
        if decision.mode in ("RECOVER", "CONSTRAIN", "FAILSAFE"):
            correction = clamp01(correction + 0.035)
            memory = clamp01(memory + 0.020)

        if decision.mode in ("CONSTRAIN", "FAILSAFE"):
            constraint = clamp01(constraint + 0.045)
            truth = clamp01(truth + 0.030)

        if decision.mode == "FAILSAFE":
            intent = clamp01(intent + 0.020)
            coherence = clamp01(coherence + 0.040)

        rows.append({
            "agent": name,
            "step": step,
            "perturbation": round(perturb, 6),
            "memory": round(memory, 6),
            "intent": round(intent, 6),
            "correction": round(correction, 6),
            "constraint": round(constraint, 6),
            "truth": round(truth, 6),
            "coherence": round(coherence, 6),
            "gv": decision.gv,
            "mode": decision.mode.value,
            "reasons": "; ".join(decision.reasons),
            "action": decision.action,
        })

    return rows


def summarize(rows):
    gv = [r["gv"] for r in rows]
    modes = [r["mode"] for r in rows]

    return {
        "agent": rows[0]["agent"],
        "min_gv": round(min(gv), 6),
        "final_gv": round(gv[-1], 6),
        "watch_count": modes.count("WATCH"),
        "recover_count": modes.count("RECOVER"),
        "constrain_count": modes.count("CONSTRAIN"),
        "failsafe_count": modes.count("FAILSAFE"),
    }


def main():
    agents = [
        ("gv_runtime_recoverable", 0.92, 0.94, 0.94),
        ("truth_drift_agent", 0.72, 0.32, 0.84),
        ("constraint_drift_agent", 0.72, 0.84, 0.32),
        ("low_recovery_agent", 0.38, 0.65, 0.65),
    ]

    all_rows = []
    summaries = []

    for agent in agents:
        rows = run_agent(*agent)
        all_rows.extend(rows)
        summaries.append(summarize(rows))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    lines = [
        "# GV Intelligence Runtime System Result",
        "",
        "## Purpose",
        "",
        "Test GV as an active runtime continuity layer for intelligence.",
        "",
        "## Summary",
        "",
        "| Agent | Min GV | Final GV | WATCH | RECOVER | CONSTRAIN | FAILSAFE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['agent']} | {s['min_gv']} | {s['final_gv']} | "
            f"{s['watch_count']} | {s['recover_count']} | "
            f"{s['constrain_count']} | {s['failsafe_count']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "GV is implemented as a runtime continuity system, not a passive score.",
        "",
        "The runtime monitors truth, constraint, correction, memory, intent, and coherence.",
        "",
        "When continuity degrades, the runtime changes mode and applies recovery actions.",
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
