import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_phase_map/TOPOLOGY_ATTRACTOR_PHASE_MAP_RESULT.md")
OUT_CSV = Path("reports/gv_phase_map/topology_attractor_phase_map.csv")

SEED = 42
rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


SYSTEMS = [
    "competitive",
    "antifragile",
    "recursive",
    "unification",
]


def system_score(
    system,
    scarcity,
    visibility,
    coupling,
    fragmentation,
):
    """
    Simple topology-phase estimator.

    The point is not realism.
    The point is discovering attractor transitions.
    """

    if system == "competitive":
        score = (
            1.25 * scarcity
            + 1.10 * fragmentation
            - 0.90 * coupling
            - 0.75 * visibility
        )

    elif system == "antifragile":
        score = (
            0.90 * scarcity
            + 0.95 * fragmentation
            + 0.45 * visibility
            - 0.35 * coupling
        )

    elif system == "recursive":
        score = (
            1.15 * visibility
            + 0.85 * coupling
            - 0.70 * scarcity
            - 0.40 * fragmentation
        )

    elif system == "unification":
        score = (
            1.25 * coupling
            + 1.20 * visibility
            - 0.85 * fragmentation
            - 0.60 * scarcity
        )

    else:
        raise ValueError(system)

    noise = rng.normal(0, 0.05)

    return score + noise


def classify_phase(
    scarcity,
    visibility,
    coupling,
    fragmentation,
):
    scores = {
        s: system_score(
            s,
            scarcity,
            visibility,
            coupling,
            fragmentation,
        )
        for s in SYSTEMS
    }

    winner = max(scores.items(), key=lambda x: x[1])[0]

    return winner, scores


def main():

    rows = []

    phase_counts = {
        s: 0
        for s in SYSTEMS
    }

    # Sweep topology-space.
    values = np.linspace(0.0, 1.0, 11)

    for scarcity in values:
        for visibility in values:
            for coupling in values:
                for fragmentation in values:

                    winner, scores = classify_phase(
                        scarcity,
                        visibility,
                        coupling,
                        fragmentation,
                    )

                    phase_counts[winner] += 1

                    rows.append({
                        "scarcity": round(float(scarcity), 2),
                        "visibility": round(float(visibility), 2),
                        "coupling": round(float(coupling), 2),
                        "fragmentation": round(float(fragmentation), 2),
                        "winner": winner,
                        "competitive_score": round(scores["competitive"], 6),
                        "antifragile_score": round(scores["antifragile"], 6),
                        "recursive_score": round(scores["recursive"], 6),
                        "unification_score": round(scores["unification"], 6),
                    })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )

        writer.writeheader()
        writer.writerows(rows)

    dominant = max(
        phase_counts.items(),
        key=lambda x: x[1],
    )[0]

    total = sum(phase_counts.values())

    lines = [
        "# GV Topology Attractor Phase Map Result",
        "",
        "## Purpose",
        "",
        "Map which topology conditions generate different intelligence attractors.",
        "",
        "## Attractor Counts",
        "",
        "| System | Winning Topology Regions | Percent |",
        "|---|---:|---:|",
    ]

    for system, count in phase_counts.items():

        pct = round(100 * count / total, 2)

        lines.append(
            f"| {system} | {count} | {pct}% |"
        )

    lines += [
        "",
        "## Dominant Global Attractor",
        "",
        f"`{dominant}`",
        "",
        "## Interpretation",
        "",
        "Different topology structures generate different intelligence phase states.",
        "",
        "Competitive extraction dominates high-scarcity fragmented topologies.",
        "",
        "Recursive and unification systems dominate high-visibility high-coupling topologies.",
        "",
        "The benchmark suggests intelligence architectures are topology-dependent attractors, not universal fixed behaviors.",
        "",
        "## Strongest GV Base",
        "",
        "> Intelligence behaviors may emerge as topology-phase states of survivability geometry.",
    ]

    OUT_MD.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print({
        "dominant": dominant,
        "phase_counts": phase_counts,
    })

    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
