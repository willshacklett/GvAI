import csv
from pathlib import Path

OUT_MD = Path("reports/gv_foundation/FOUNDATION_AXIOM_SCORECARD.md")
OUT_CSV = Path("reports/gv_foundation/foundation_axiom_scorecard.csv")

AXIOMS = [
    {
        "axiom": "Persistence requires continuity",
        "status": "ACTIVE_FOUNDATION",
        "support": "All surviving GV formulations depend on continuity relations.",
    },
    {
        "axiom": "Recoverability is structurally meaningful",
        "status": "SUPPORTED",
        "support": "Collapse and transition experiments repeatedly depended on recovery behavior.",
    },
    {
        "axiom": "Irreversible degradation is distinguishable",
        "status": "SUPPORTED_PARTIAL",
        "support": "Directional degradation and persistence filters improved separation.",
    },
    {
        "axiom": "Continuity survives harmless transformation",
        "status": "SUPPORTED",
        "support": "Order-invariant tests survived scale/monotonic/noise transforms.",
    },
    {
        "axiom": "Arbitrary coordinates are not sacred",
        "status": "SUPPORTED",
        "support": "Rotation attacks fractured continuity order while meaningful axes remained stable.",
    },
    {
        "axiom": "Local continuity may diverge from global continuity",
        "status": "SUPPORTED",
        "support": "Hypergraph and panarchy experiments showed hidden global strain.",
    },
    {
        "axiom": "Observable behavior incompletely reveals hidden state",
        "status": "SUPPORTED",
        "support": "Latent-state inference experiments failed full reconstruction.",
    },
]

def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["axiom", "status", "support"],
        )
        writer.writeheader()
        writer.writerows(AXIOMS)

    lines = [
        "# GV Foundation Axiom Scorecard",
        "",
        "## Purpose",
        "",
        "Define the minimal continuity foundation beneath GV.",
        "",
        "## Axiom Results",
        "",
        "| Axiom | Status | Evidence |",
        "|---|---|---|",
    ]

    for a in AXIOMS:
        lines.append(
            f"| {a['axiom']} | {a['status']} | {a['support']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "The project is converging toward continuity axioms rather than one fitted scalar.",
        "",
        "The strongest surviving GV direction is:",
        "",
        "> persistent existence requires continuity-preserving structure",
        "",
        "while recoverability, ordering, topology, and scale relations emerge as downstream expressions.",
        "",
        "## Scientific Rule",
        "",
        "Do not protect the axioms from falsification.",
        "",
        "Do not collapse the foundation into arbitrary tuning.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "axioms": len(AXIOMS),
        "out": str(OUT_MD),
    })

if __name__ == "__main__":
    main()
