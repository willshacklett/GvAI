import csv
from pathlib import Path

OUT_MD = Path("reports/gv_toe/TOE_FOUNDATION_SCORECARD.md")
OUT_CSV = Path("reports/gv_toe/toe_foundation_scorecard.csv")

CHECKS = [
    {
        "claim": "Weighted scalar GV is invariant",
        "status": "FAILED",
        "evidence": "Continuity invariance test failed under scale/monotonic/noise transforms.",
        "meaning": "Do not treat tuned scalar GV as the foundation.",
    },
    {
        "claim": "Recoverability geometry is low-dimensional",
        "status": "SUPPORTED_PARTIAL",
        "evidence": "Geometry audits repeatedly showed high PC1 variance.",
        "meaning": "Compression exists, but may not uniquely privilege GV.",
    },
    {
        "claim": "GV scalar is mathematically privileged",
        "status": "NOT_YET",
        "evidence": "Hostile null models showed GV above average but not privileged.",
        "meaning": "Scalar projection is not enough for TOE.",
    },
    {
        "claim": "Continuity order survives harmless transforms",
        "status": "SUPPORTED",
        "evidence": "Order-invariant test survived scale, monotonic, noise, and exceeded nulls.",
        "meaning": "Relational continuity is stronger than tuned scalar framing.",
    },
    {
        "claim": "Continuity is fully coordinate-free",
        "status": "FAILED_PARTIAL",
        "evidence": "Core order attack fractured under rotation and incomparability attacks.",
        "meaning": "Continuity likely depends on structured/causal axes, not arbitrary coordinates.",
    },
    {
        "claim": "Local health equals global health",
        "status": "FAILED",
        "evidence": "Panarchy/hypergraph tests showed large local-global GV gaps.",
        "meaning": "TOE-level GV must handle scale separation.",
    },
    {
        "claim": "Observable behavior perfectly reveals hidden state",
        "status": "FAILED",
        "evidence": "Latent-state inference lost to a simple baseline.",
        "meaning": "GV can detect continuity leakage without fully reconstructing hidden state.",
    },
    {
        "claim": "Persistent existence requires continuity structure",
        "status": "ACTIVE_HYPOTHESIS",
        "evidence": "No current test has disproven the foundational continuity requirement.",
        "meaning": "This remains the core TOE-level claim.",
    },
]

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["claim", "status", "evidence", "meaning"],
        )
        writer.writeheader()
        writer.writerows(CHECKS)

    lines = [
        "# GV TOE Foundation Scorecard",
        "",
        "## Purpose",
        "",
        "Keep TOE as the horizon while refusing to hide failures.",
        "",
        "## Scorecard",
        "",
        "| Claim | Status | Evidence | Meaning |",
        "|---|---|---|---|",
    ]

    for c in CHECKS:
        lines.append(
            f"| {c['claim']} | {c['status']} | {c['evidence']} | {c['meaning']} |"
        )

    lines += [
        "",
        "## Current TOE-Level Interpretation",
        "",
        "The strongest surviving form of GV is not a tuned scalar.",
        "",
        "The strongest surviving form is:",
        "",
        "> Persistent existence requires continuity-preserving structure.",
        "",
        "That structure may express as scalar, order, topology, causal relation, or scale-coupled recoverability.",
        "",
        "## Next Requirement",
        "",
        "Build tests that look for continuity-preserving structure across domains without assuming the form in advance.",
        "",
        "## Rule",
        "",
        "Do not reduce the TOE target.",
        "",
        "Do not fake proof.",
        "",
        "Let GV stand or fall against the hardest tests.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"written": str(OUT_MD), "checks": len(CHECKS)})

if __name__ == "__main__":
    main()
