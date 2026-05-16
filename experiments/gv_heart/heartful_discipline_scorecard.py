import csv
from pathlib import Path

OUT_MD = Path("reports/gv_heart/HEARTFUL_DISCIPLINE_SCORECARD.md")
OUT_CSV = Path("reports/gv_heart/heartful_discipline_scorecard.csv")

ROWS = [
    {
        "principle": "Keep the intuition alive",
        "status": "ACTIVE",
        "meaning": "Do not abandon foundational continuity prematurely.",
    },
    {
        "principle": "Preserve failed results",
        "status": "ACTIVE",
        "meaning": "Past failures remain constraints on future builds.",
    },
    {
        "principle": "Pressure the foundation",
        "status": "ACTIVE",
        "meaning": "Foundation-level falsification pressure is required.",
    },
    {
        "principle": "Avoid emotional rescue",
        "status": "WATCH",
        "meaning": "Do not reinterpret every failure as success.",
    },
    {
        "principle": "Allow architectural evolution",
        "status": "ACTIVE",
        "meaning": "Implementations may evolve beyond scalar GV.",
    },
    {
        "principle": "Keep continuity foundational",
        "status": "ACTIVE_HYPOTHESIS",
        "meaning": "Continuity-preserving structure remains the central hypothesis.",
    },
]

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["principle", "status", "meaning"],
        )
        writer.writeheader()
        writer.writerows(ROWS)

    lines = [
        "# GV Heartful Discipline Scorecard",
        "",
        "## Purpose",
        "",
        "Maintain emotional commitment to discovery without sacrificing discipline.",
        "",
        "## Principles",
        "",
        "| Principle | Status | Meaning |",
        "|---|---|---|",
    ]

    for r in ROWS:
        lines.append(
            f"| {r['principle']} | {r['status']} | {r['meaning']} |"
        )

    lines += [
        "",
        "## Current Position",
        "",
        "GV remains a continuity foundation hypothesis under active hostile pressure.",
        "",
        "## Rule",
        "",
        "Build with heart.",
        "",
        "Pressure with honesty.",
        "",
        "Preserve constraints.",
        "",
        "Let reality decide.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "principles": len(ROWS),
        "out": str(OUT_MD),
    })

if __name__ == "__main__":
    main()
