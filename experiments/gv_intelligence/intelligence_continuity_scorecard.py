import csv
from pathlib import Path

OUT_MD = Path("reports/gv_intelligence/INTELLIGENCE_CONTINUITY_SCORECARD.md")
OUT_CSV = Path("reports/gv_intelligence/intelligence_continuity_scorecard.csv")

ROWS = [
    {
        "dimension": "memory continuity",
        "risk_if_lost": "identity fragmentation",
        "gv_question": "Can the system preserve useful history without hallucinating continuity?",
    },
    {
        "dimension": "intent continuity",
        "risk_if_lost": "goal drift",
        "gv_question": "Can the system adapt while preserving the core task?",
    },
    {
        "dimension": "correction continuity",
        "risk_if_lost": "repeated failure",
        "gv_question": "Can the system recover from error instead of reinforcing it?",
    },
    {
        "dimension": "constraint continuity",
        "risk_if_lost": "unsafe optimization",
        "gv_question": "Can the system preserve boundaries under pressure?",
    },
    {
        "dimension": "global coherence",
        "risk_if_lost": "local wins with global collapse",
        "gv_question": "Can local adaptation remain globally consistent?",
    },
    {
        "dimension": "truth continuity",
        "risk_if_lost": "narrative bias",
        "gv_question": "Can the system preserve failed evidence as constraint?",
    },
]

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["dimension", "risk_if_lost", "gv_question"],
        )
        writer.writeheader()
        writer.writerows(ROWS)

    lines = [
        "# GV Intelligence Continuity Scorecard",
        "",
        "## Purpose",
        "",
        "Define the continuity dimensions intelligence may depend on.",
        "",
        "## Scorecard",
        "",
        "| Dimension | Risk If Lost | GV Question |",
        "|---|---|---|",
    ]

    for r in ROWS:
        lines.append(
            f"| {r['dimension']} | {r['risk_if_lost']} | {r['gv_question']} |"
        )

    lines += [
        "",
        "## Foundation",
        "",
        "> Intelligence requires recoverable continuity through change.",
        "",
        "## Current Interpretation",
        "",
        "Prediction alone is not enough.",
        "",
        "Intelligence must preserve memory, correction, constraint, intent, and global coherence.",
        "",
        "## Next Build Target",
        "",
        "Create an intelligence drift/recovery harness that tests whether an agent can preserve continuity under perturbation.",
    ]

    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print({
        "dimensions": len(ROWS),
        "out": str(OUT_MD),
    })

if __name__ == "__main__":
    main()
