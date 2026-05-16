import csv
from pathlib import Path

OUT_MD = Path("reports/gv_right_or_wrong/RIGHT_OR_WRONG_SCORECARD.md")
OUT_CSV = Path("reports/gv_right_or_wrong/right_or_wrong_scorecard.csv")

ROWS = [
    {
        "question": "Can local continuity fake persistence?",
        "status": "YES",
        "meaning": "Local overlap alone is insufficient.",
    },
    {
        "question": "Can fragmentation hide under local stability?",
        "status": "YES",
        "meaning": "Global continuation matters.",
    },
    {
        "question": "Can randomization inflate coherence?",
        "status": "YES",
        "meaning": "Homogenization can mimic persistence.",
    },
    {
        "question": "Has GV been proven?",
        "status": "NO",
        "meaning": "The project remains exploratory.",
    },
    {
        "question": "Has GV been eliminated?",
        "status": "NO",
        "meaning": "Continuity still generates unresolved distinctions.",
    },
    {
        "question": "Does the foundation remain testable?",
        "status": "YES",
        "meaning": "Bias audits and kill criteria remain active requirements.",
    },
]

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["question", "status", "meaning"],
        )
        writer.writeheader()
        writer.writerows(ROWS)

    lines = [
        "# GV Right or Wrong Scorecard",
        "",
        "## Purpose",
        "",
        "Keep the project capable of discovering both success and failure honestly.",
        "",
        "## Current Answers",
        "",
        "| Question | Status | Meaning |",
        "|---|---|---|",
    ]

    for r in ROWS:
        lines.append(
            f"| {r['question']} | {r['status']} | {r['meaning']} |"
        )

    lines += [
        "",
        "## Current Foundation",
        "",
        "> Persistent existence requires continuity-preserving structure.",
        "",
        "## Current Position",
        "",
        "The project remains under hostile pressure.",
        "",
        "Reality has not answered fully yet.",
        "",
        "## Rule",
        "",
        "Do not fake certainty.",
        "",
        "Do not abandon the search prematurely.",
        "",
        "Build honestly enough to discover whether GV is right or wrong.",
    ]

    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    print({
        "questions": len(ROWS),
        "out": str(OUT_MD),
    })

if __name__ == "__main__":
    main()
