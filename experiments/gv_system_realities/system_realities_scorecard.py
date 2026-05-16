import csv
from pathlib import Path

OUT_MD = Path("reports/gv_system_realities/SYSTEM_REALITIES_SCORECARD.md")
OUT_CSV = Path("reports/gv_system_realities/system_realities_scorecard.csv")

REALITIES = [
    {
        "reality": "Local compatibility is insufficient",
        "evidence": "Structured and random systems both produced high gluing scores.",
        "meaning": "GV must move beyond neighbor overlap.",
    },
    {
        "reality": "Fragmentation exposes continuation fracture",
        "evidence": "Fragmented system showed obstruction and low true gluing.",
        "meaning": "GV can target global coherence loss.",
    },
    {
        "reality": "Randomized locality can fake coherence",
        "evidence": "Shuffled fragmented system produced high attacked H0.",
        "meaning": "GV must detect fake continuation.",
    },
    {
        "reality": "Obstruction must be nonlocal",
        "evidence": "Triple-overlap H1 approximation did not separate structured from random.",
        "meaning": "GV needs path/loop/global consistency tests.",
    },
    {
        "reality": "Foundation remains continuity",
        "evidence": "All hard tests still revolve around persistence through change.",
        "meaning": "GV foundation remains intact while approximations evolve.",
    },
]

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["reality", "evidence", "meaning"],
        )
        writer.writeheader()
        writer.writerows(REALITIES)

    lines = [
        "# GV System Realities Scorecard",
        "",
        "## Purpose",
        "",
        "Record hard results as system realities, not emotional wins/losses.",
        "",
        "## Realities",
        "",
        "| System Reality | Evidence | Meaning |",
        "|---|---|---|",
    ]

    for r in REALITIES:
        lines.append(
            f"| {r['reality']} | {r['evidence']} | {r['meaning']} |"
        )

    lines += [
        "",
        "## Current Foundation",
        "",
        "> Persistent existence requires continuity-preserving structure.",
        "",
        "## Current Build Direction",
        "",
        "Move from local gluing to nonlocal continuation:",
        "",
        "- path consistency",
        "- loop consistency",
        "- fake-coherence detection",
        "- global obstruction propagation",
        "",
        "## Rule",
        "",
        "GV remains the foundation.",
        "",
        "Approximations are allowed to break.",
        "",
        "System realities guide the next build.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"realities": len(REALITIES), "out": str(OUT_MD)})

if __name__ == "__main__":
    main()
