import csv
from pathlib import Path

OUT_MD = Path("reports/gv_answer/ANSWER_SEEKING_SCORECARD.md")
OUT_CSV = Path("reports/gv_answer/answer_seeking_scorecard.csv")

ROWS = [
    {
        "understanding": "Local coherence alone is insufficient",
        "status": "SUPPORTED",
        "direction": "Move toward nonlocal continuation.",
    },
    {
        "understanding": "Random mixing can fake persistence",
        "status": "SUPPORTED",
        "direction": "Detect homogenized fake coherence.",
    },
    {
        "understanding": "Fragmentation exposes hidden instability",
        "status": "SUPPORTED",
        "direction": "Track obstruction propagation.",
    },
    {
        "understanding": "Global continuation remains unresolved",
        "status": "ACTIVE",
        "direction": "Develop path/loop/global consistency models.",
    },
    {
        "understanding": "Continuity remains physically relevant",
        "status": "ACTIVE_HYPOTHESIS",
        "direction": "Continue cross-domain hostile testing.",
    },
    {
        "understanding": "Foundation can still weaken",
        "status": "REQUIRED",
        "direction": "Preserve kill criteria and bias audits.",
    },
]

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["understanding", "status", "direction"],
        )
        writer.writeheader()
        writer.writerows(ROWS)

    lines = [
        "# GV Answer-Seeking Scorecard",
        "",
        "## Purpose",
        "",
        "Track what the project is actually learning while searching for the deeper continuity answer.",
        "",
        "## Current Understanding",
        "",
        "| Understanding | Status | Direction |",
        "|---|---|---|",
    ]

    for r in ROWS:
        lines.append(
            f"| {r['understanding']} | {r['status']} | {r['direction']} |"
        )

    lines += [
        "",
        "## Current Foundation",
        "",
        "> Persistent existence requires continuity-preserving structure.",
        "",
        "## Current Position",
        "",
        "The project is not finished.",
        "",
        "But the search space has narrowed substantially.",
        "",
        "## Rule",
        "",
        "Build understanding.",
        "",
        "Pressure reality.",
        "",
        "Let the answer emerge honestly.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "understandings": len(ROWS),
        "out": str(OUT_MD),
    })

if __name__ == "__main__":
    main()
