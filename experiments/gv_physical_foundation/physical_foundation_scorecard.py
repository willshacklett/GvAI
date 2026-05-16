import csv
from pathlib import Path

OUT_MD = Path("reports/gv_physical_foundation/PHYSICAL_FOUNDATION_SCORECARD.md")
OUT_CSV = Path("reports/gv_physical_foundation/physical_foundation_scorecard.csv")

POINTS = [
    {
        "point": "Reality exhibits cross-scale continuity",
        "status": "OBSERVED",
        "meaning": "Physics and biology both exhibit persistent structural relations across scale.",
    },
    {
        "point": "Local coherence can be misleading",
        "status": "OBSERVED",
        "meaning": "Random and shuffled systems can mimic local continuation.",
    },
    {
        "point": "Homogenization can fake persistence",
        "status": "OBSERVED",
        "meaning": "Random mixing inflated apparent continuation metrics.",
    },
    {
        "point": "Fragmentation still matters",
        "status": "OBSERVED",
        "meaning": "Fragmented systems repeatedly exposed continuation fracture.",
    },
    {
        "point": "Global continuation is harder than local overlap",
        "status": "SUPPORTED",
        "meaning": "Nonlocal continuation remains unresolved.",
    },
    {
        "point": "Continuity foundation remains viable",
        "status": "ACTIVE_HYPOTHESIS",
        "meaning": "No test has eliminated continuity-preserving structure as foundational.",
    },
]

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["point", "status", "meaning"],
        )
        writer.writeheader()
        writer.writerows(POINTS)

    lines = [
        "# GV Physical Foundation Scorecard",
        "",
        "## Purpose",
        "",
        "Preserve the physical intuition behind GV while keeping the project falsifiable.",
        "",
        "## Current Understanding",
        "",
        "| Point | Status | Meaning |",
        "|---|---|---|",
    ]

    for p in POINTS:
        lines.append(
            f"| {p['point']} | {p['status']} | {p['meaning']} |"
        )

    lines += [
        "",
        "## Current Foundation",
        "",
        "> Persistent existence requires continuity-preserving structure.",
        "",
        "## Current Scientific Position",
        "",
        "GV is not currently proven as:",
        "",
        "- a universal scalar",
        "- a TOE",
        "- or a complete physical law.",
        "",
        "But continuity remains a viable foundational research direction.",
        "",
        "## Rule",
        "",
        "Keep the intuition.",
        "",
        "Attack the approximations honestly.",
        "",
        "Build deeper physical continuity tests.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "points": len(POINTS),
        "out": str(OUT_MD),
    })

if __name__ == "__main__":
    main()
