import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_nonlocal/NONLOCAL_CONTINUATION_RESULT.md")
OUT_CSV = Path("reports/gv_nonlocal/nonlocal_continuation_result.csv")

SEED = 42
ROWS = 220

rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def make_structured_system():
    rows = []

    for t in range(ROWS):
        phase = t / ROWS

        continuity = clamp01(
            0.88
            - 0.68 * phase
            + rng.normal(0, 0.025)
        )

        rows.append([
            continuity + rng.normal(0, 0.03),
            continuity + rng.normal(0, 0.03),
            continuity + rng.normal(0, 0.03),
            1.0 - continuity + rng.normal(0, 0.03),
        ])

    return np.clip(np.array(rows), 0, 1)


def make_random_system():
    return rng.uniform(0, 1, size=(ROWS, 4))


def make_fragmented_system():
    rows = []

    for t in range(ROWS):
        if (t // 18) % 2 == 0:
            base = 0.82
        else:
            base = 0.18

        rows.append([
            clamp01(base + rng.normal(0, 0.07)),
            clamp01((1.0 - base) + rng.normal(0, 0.07)),
            clamp01(base + rng.normal(0, 0.07)),
            clamp01((1.0 - base) + rng.normal(0, 0.07)),
        ])

    return np.array(rows)


def sectionize(matrix, window=10):
    sections = []

    for i in range(0, len(matrix) - window, window):
        sections.append(
            np.mean(matrix[i:i+window], axis=0)
        )

    return sections


def overlap(a, b):
    dist = np.mean(np.abs(a - b))
    return 1.0 - clamp01(dist)


def long_path_consistency(sections):
    '''
    Nonlocal continuation:
    distant sections should remain path-coherent.
    '''
    scores = []

    for i in range(len(sections)):
        for j in range(i + 3, len(sections)):
            scores.append(
                overlap(sections[i], sections[j])
            )

    return float(np.mean(scores)) if scores else 0.0


def loop_consistency(sections):
    '''
    Approximate loop closure consistency.

    If A≈B and B≈C but A diverges from C,
    continuation coherence weakens.
    '''
    penalties = []

    for i in range(len(sections) - 4):
        a = sections[i]
        b = sections[i + 2]
        c = sections[i + 4]

        ab = overlap(a, b)
        bc = overlap(b, c)
        ac = overlap(a, c)

        inconsistency = abs((ab + bc)/2 - ac)

        penalties.append(inconsistency)

    return 1.0 - float(np.mean(penalties)) if penalties else 0.0


def locality_attack(matrix):
    idx = np.arange(len(matrix))
    rng.shuffle(idx)
    return matrix[idx]


def evaluate(name, matrix):
    sections = sectionize(matrix)

    path_score = long_path_consistency(sections)
    loop_score = loop_consistency(sections)

    attacked = locality_attack(matrix)

    attacked_sections = sectionize(attacked)

    attacked_path = long_path_consistency(attacked_sections)
    attacked_loop = loop_consistency(attacked_sections)

    advantage = (
        (path_score - attacked_path)
        + (loop_score - attacked_loop)
    ) / 2

    if advantage > 0.10:
        result = "NONLOCAL_CONTINUATION_DIFFERENTIATED"
    elif advantage > 0.03:
        result = "PARTIAL_NONLOCAL_ADVANTAGE"
    else:
        result = "NO_NONLOCAL_ADVANTAGE"

    return {
        "system": name,
        "path_score": round(path_score, 6),
        "loop_score": round(loop_score, 6),
        "attacked_path": round(attacked_path, 6),
        "attacked_loop": round(attacked_loop, 6),
        "advantage": round(advantage, 6),
        "result": result,
    }


def main():
    rows = []

    rows.append(
        evaluate(
            "structured_continuity",
            make_structured_system()
        )
    )

    rows.append(
        evaluate(
            "random_system",
            make_random_system()
        )
    )

    rows.append(
        evaluate(
            "fragmented_system",
            make_fragmented_system()
        )
    )

    structured = rows[0]

    if structured["result"] == "NONLOCAL_CONTINUATION_DIFFERENTIATED":
        final = "NONLOCAL_CONTINUATION_SUPPORTED"
    elif structured["result"] == "PARTIAL_NONLOCAL_ADVANTAGE":
        final = "PARTIAL_NONLOCAL_SIGNAL"
    else:
        final = "NO_NONLOCAL_DIFFERENTIATION"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# GV Nonlocal Continuation Result",
        "",
        "## Purpose",
        "",
        "Test whether nonlocal continuation structure distinguishes authentic persistence from fake local compatibility.",
        "",
        "## Final Result",
        "",
        f"`{final}`",
        "",
        "## Results",
        "",
        "| System | Path Score | Loop Score | Attacked Path | Attacked Loop | Advantage | Result |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    for r in rows:
        lines.append(
            f"| {r['system']} | {r['path_score']} | "
            f"{r['loop_score']} | {r['attacked_path']} | "
            f"{r['attacked_loop']} | {r['advantage']} | "
            f"{r['result']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "This test escalates from local compatibility to nonlocal continuation structure.",
        "",
        "Long-path consistency and loop consistency approximate continuation coherence over distance.",
        "",
        "Random locality attacks attempt to manufacture fake continuation.",
        "",
        "GV strengthens if authentic systems retain stronger nonlocal coherence.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "final": final,
        "rows": rows,
    })

    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
