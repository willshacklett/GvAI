import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_boundary/ANTIFRAGILE_UNIFICATION_BOUNDARY_RESULT.md")
OUT_CSV = Path("reports/gv_boundary/antifragile_unification_boundary.csv")

SEED = 42
rng = np.random.default_rng(SEED)


def score_antifragile(scarcity, visibility, coupling, fragmentation):
    return (
        0.90 * scarcity
        + 0.95 * fragmentation
        + 0.45 * visibility
        - 0.35 * coupling
        + rng.normal(0, 0.025)
    )


def score_unification(scarcity, visibility, coupling, fragmentation):
    return (
        1.25 * coupling
        + 1.20 * visibility
        - 0.85 * fragmentation
        - 0.60 * scarcity
        + rng.normal(0, 0.025)
    )


def main():
    rows = []

    values = np.linspace(0.0, 1.0, 21)

    flips = []

    for scarcity in values:
        for fragmentation in values:
            for visibility in values:
                for coupling in values:
                    anti = score_antifragile(
                        scarcity,
                        visibility,
                        coupling,
                        fragmentation,
                    )

                    uni = score_unification(
                        scarcity,
                        visibility,
                        coupling,
                        fragmentation,
                    )

                    margin = uni - anti

                    winner = "unification" if margin > 0 else "antifragile"

                    near_boundary = abs(margin) <= 0.05

                    row = {
                        "scarcity": round(float(scarcity), 2),
                        "fragmentation": round(float(fragmentation), 2),
                        "visibility": round(float(visibility), 2),
                        "coupling": round(float(coupling), 2),
                        "antifragile_score": round(float(anti), 6),
                        "unification_score": round(float(uni), 6),
                        "margin_unification_minus_antifragile": round(float(margin), 6),
                        "winner": winner,
                        "near_boundary": near_boundary,
                    }

                    rows.append(row)

                    if near_boundary:
                        flips.append(row)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)

    # Summarize boundary conditions
    if flips:
        avg = {
            "scarcity": round(float(np.mean([r["scarcity"] for r in flips])), 4),
            "fragmentation": round(float(np.mean([r["fragmentation"] for r in flips])), 4),
            "visibility": round(float(np.mean([r["visibility"] for r in flips])), 4),
            "coupling": round(float(np.mean([r["coupling"] for r in flips])), 4),
        }
    else:
        avg = {
            "scarcity": None,
            "fragmentation": None,
            "visibility": None,
            "coupling": None,
        }

    unification_count = sum(1 for r in rows if r["winner"] == "unification")
    antifragile_count = sum(1 for r in rows if r["winner"] == "antifragile")
    total = len(rows)

    lines = [
        "# GV Antifragile-Unification Boundary Result",
        "",
        "## Purpose",
        "",
        "Find where antifragile exploration flips into unification dominance.",
        "",
        "## Attractor Counts",
        "",
        f"- antifragile regions: {antifragile_count}",
        f"- unification regions: {unification_count}",
        f"- total regions: {total}",
        f"- unification percent: {round(100 * unification_count / total, 2)}%",
        "",
        "## Boundary Count",
        "",
        f"- near-boundary regions: {len(flips)}",
        "",
        "## Average Boundary Conditions",
        "",
        "| Scarcity | Fragmentation | Future Visibility | Recoverability Coupling |",
        "|---:|---:|---:|---:|",
        f"| {avg['scarcity']} | {avg['fragmentation']} | {avg['visibility']} | {avg['coupling']} |",
        "",
        "## Interpretation",
        "",
        "This boundary estimates when intelligence shifts from surviving disorder through antifragility",
        "to preserving shared future accessibility through unification.",
        "",
        "High visibility and high recoverability coupling push systems toward unification.",
        "",
        "High scarcity and fragmentation push systems toward antifragile dominance.",
        "",
        "## Strong GV Base",
        "",
        "> GV may be the transition structure that converts fragmented survivability into shared future accessibility.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "antifragile_regions": antifragile_count,
        "unification_regions": unification_count,
        "boundary_regions": len(flips),
        "avg_boundary": avg,
    })

    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
