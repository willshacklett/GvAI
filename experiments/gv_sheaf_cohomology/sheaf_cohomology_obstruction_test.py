import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_sheaf_cohomology/SHEAF_COHOMOLOGY_RESULT.md")
OUT_CSV = Path("reports/gv_sheaf_cohomology/sheaf_cohomology_result.csv")

SEED = 42
ROWS = 180

rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def make_structured_system():
    rows = []

    for t in range(ROWS):
        phase = t / ROWS

        continuity = clamp01(
            0.85
            - 0.60 * phase
            + rng.normal(0, 0.03)
        )

        rows.append([
            continuity + rng.normal(0, 0.04),
            continuity + rng.normal(0, 0.04),
            continuity + rng.normal(0, 0.04),
            1.0 - continuity + rng.normal(0, 0.04),
        ])

    return np.clip(np.array(rows), 0, 1)


def make_random_system():
    return rng.uniform(0, 1, size=(ROWS, 4))


def make_fragmented_system():
    rows = []

    for t in range(ROWS):
        phase = (t // 15) % 2

        if phase == 0:
            base = 0.85
        else:
            base = 0.15

        rows.append([
            clamp01(base + rng.normal(0, 0.08)),
            clamp01((1.0 - base) + rng.normal(0, 0.08)),
            clamp01(base + rng.normal(0, 0.08)),
            clamp01((1.0 - base) + rng.normal(0, 0.08)),
        ])

    return np.array(rows)


def build_sections(matrix, window=12):
    sections = []

    for i in range(0, len(matrix) - window, window):
        section = np.mean(matrix[i:i+window], axis=0)
        sections.append(section)

    return sections


def overlap_score(a, b):
    dist = np.mean(np.abs(a - b))
    return 1.0 - clamp01(dist)


def cocycle_obstruction(sections, threshold=0.72):
    '''
    Approximate H1-like obstruction signal.

    Triple overlaps must remain mutually compatible.

    Pairwise overlap alone is insufficient.
    '''
    obstructions = 0
    checks = 0

    for i in range(len(sections) - 2):
        a = sections[i]
        b = sections[i + 1]
        c = sections[i + 2]

        ab = overlap_score(a, b)
        bc = overlap_score(b, c)
        ac = overlap_score(a, c)

        # Obstruction:
        # pairwise compatibility exists,
        # but long-range consistency breaks.
        if ab > threshold and bc > threshold and ac < threshold:
            obstructions += 1

        checks += 1

    return obstructions / checks if checks else 0.0


def h0_continuation_strength(sections):
    overlaps = []

    for i in range(len(sections) - 1):
        overlaps.append(
            overlap_score(
                sections[i],
                sections[i + 1]
            )
        )

    return float(np.mean(overlaps)) if overlaps else 0.0


def random_cover_attack(matrix):
    idx = np.arange(len(matrix))
    rng.shuffle(idx)
    return matrix[idx]


def evaluate(name, matrix):
    sections = build_sections(matrix)

    h0 = h0_continuation_strength(sections)
    h1 = cocycle_obstruction(sections)

    attacked = random_cover_attack(matrix)

    attacked_sections = build_sections(attacked)

    attacked_h0 = h0_continuation_strength(attacked_sections)
    attacked_h1 = cocycle_obstruction(attacked_sections)

    if h0 > attacked_h0 and h1 < attacked_h1:
        result = "GLOBAL_CONTINUATION_DIFFERENTIATED"
    elif h1 < attacked_h1:
        result = "PARTIAL_OBSTRUCTION_ADVANTAGE"
    else:
        result = "NO_OBSTRUCTION_ADVANTAGE"

    return {
        "system": name,
        "h0_strength": round(h0, 6),
        "h1_obstruction": round(h1, 6),
        "attacked_h0": round(attacked_h0, 6),
        "attacked_h1": round(attacked_h1, 6),
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

    if structured["result"] == "GLOBAL_CONTINUATION_DIFFERENTIATED":
        final = "OBSTRUCTION_SENSITIVE_CONTINUATION_SUPPORTED"
    elif structured["result"] == "PARTIAL_OBSTRUCTION_ADVANTAGE":
        final = "PARTIAL_OBSTRUCTION_SIGNAL"
    else:
        final = "NO_OBSTRUCTION_DIFFERENTIATION"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# GV Sheaf Cohomology Result",
        "",
        "## Purpose",
        "",
        "Test whether obstruction-sensitive continuation distinguishes structured persistence from random organization.",
        "",
        "## Final Result",
        "",
        f"`{final}`",
        "",
        "## Results",
        "",
        "| System | H0 Strength | H1 Obstruction | Attacked H0 | Attacked H1 | Result |",
        "|---|---:|---:|---:|---:|---|",
    ]

    for r in rows:
        lines.append(
            f"| {r['system']} | {r['h0_strength']} | "
            f"{r['h1_obstruction']} | {r['attacked_h0']} | "
            f"{r['attacked_h1']} | {r['result']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "H0 approximates global continuation strength.",
        "",
        "H1 approximates obstruction to continuation.",
        "",
        "This moves beyond simple local overlap into consistency across triple overlaps.",
        "",
        "The goal is to distinguish authentic continuation from random local compatibility.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "final": final,
        "rows": rows,
    })

    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
