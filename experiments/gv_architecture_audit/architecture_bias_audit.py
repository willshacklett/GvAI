import csv
from pathlib import Path

OUT_MD = Path("reports/gv_architecture_audit/ARCHITECTURE_BIAS_AUDIT.md")
OUT_CSV = Path("reports/gv_architecture_audit/architecture_bias_audit.csv")

CHECKS = [
    {
        "risk": "Foundation protected from all failures",
        "status": "WATCH",
        "evidence": "Several failed approximations were reclassified as system realities.",
        "correction": "Define explicit foundation-level falsification triggers.",
    },
    {
        "risk": "Scalar failure ignored",
        "status": "CONTROLLED",
        "evidence": "Scalar failures were documented and not used as proof.",
        "correction": "Keep scalar as implementation only.",
    },
    {
        "risk": "Random systems mimic continuity",
        "status": "ACTIVE_THREAT",
        "evidence": "Random/shuffled systems repeatedly produced high apparent coherence.",
        "correction": "Require structured systems to beat random systems under hostile nulls.",
    },
    {
        "risk": "Architecture always moves goalposts",
        "status": "WATCH",
        "evidence": "Project escalated from scalar to order to sheaf to nonlocal structure.",
        "correction": "Every escalation must preserve old failures as constraints, not erase them.",
    },
    {
        "risk": "TOE target creates confirmation pressure",
        "status": "ACTIVE_THREAT",
        "evidence": "TOE framing is emotionally and philosophically powerful.",
        "correction": "Maintain scorecards with failed/narrowed claims.",
    },
    {
        "risk": "Foundation still testable",
        "status": "PASS_FOR_NOW",
        "evidence": "Current foundation predicts persistence should require distinguishable continuity structure.",
        "correction": "Next tests must attack that prediction directly.",
    },
]

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["risk", "status", "evidence", "correction"],
        )
        writer.writeheader()
        writer.writerows(CHECKS)

    active = sum(1 for c in CHECKS if c["status"] == "ACTIVE_THREAT")
    watch = sum(1 for c in CHECKS if c["status"] == "WATCH")

    if active >= 2:
        final = "ARCHITECTURE_HAS_ACTIVE_BIAS_RISK"
    elif watch >= 2:
        final = "ARCHITECTURE_REQUIRES_BIAS_CONTROLS"
    else:
        final = "ARCHITECTURE_BIAS_CONTROLLED_FOR_NOW"

    lines = [
        "# GV Architecture Bias Audit",
        "",
        "## Purpose",
        "",
        "Test whether the project architecture is honestly scientific or biased toward preserving GV.",
        "",
        "## Final Result",
        "",
        f"`{final}`",
        "",
        "## Bias Checks",
        "",
        "| Risk | Status | Evidence | Correction |",
        "|---|---|---|---|",
    ]

    for c in CHECKS:
        lines.append(
            f"| {c['risk']} | {c['status']} | {c['evidence']} | {c['correction']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "The architecture is not automatically right.",
        "",
        "It remains acceptable only if GV continues generating risky, testable distinctions.",
        "",
        "If every failure becomes merely an approximation failure, the architecture becomes biased.",
        "",
        "## Rule Going Forward",
        "",
        "GV may remain the foundation.",
        "",
        "But the foundation must be allowed to weaken.",
        "",
        "The next build must define foundation-level kill criteria.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "final": final,
        "active_threats": active,
        "watch": watch,
        "out": str(OUT_MD),
    })

if __name__ == "__main__":
    main()
