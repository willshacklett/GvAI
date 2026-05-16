import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_sheaf/CONTINUATION_SHEAF_RESULT.md")
OUT_CSV = Path("reports/gv_sheaf/continuation_sheaf_result.csv")

SEED = 42
ROWS = 140

rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def make_structured_system():
    rows = []

    for t in range(ROWS):
        phase = t / ROWS

        continuity = clamp01(
            0.82
            - 0.55 * phase
            + rng.normal(0, 0.04)
        )

        rows.append([
            continuity + rng.normal(0, 0.05),
            continuity + rng.normal(0, 0.05),
            1.0 - continuity + rng.normal(0, 0.05),
            continuity + rng.normal(0, 0.05),
        ])

    return np.clip(np.array(rows), 0, 1)


def make_random_system():
    return rng.uniform(0, 1, size=(ROWS, 4))


def make_fragmented_system():
    rows = []

    for t in range(ROWS):
        if t % 20 < 10:
            base = 0.8
        else:
            base = 0.2

        rows.append([
            clamp01(base + rng.normal(0, 0.08)),
            clamp01((1.0 - base) + rng.normal(0, 0.08)),
            clamp01(base + rng.normal(0, 0.08)),
            clamp01((1.0 - base) + rng.normal(0, 0.08)),
        ])

    return np.array(rows)


def local_section_overlap(a, b):
    '''
    Approximate local compatibility:
    do neighboring local persistence structures agree?
    '''
    dist = np.mean(np.abs(a - b))
    return 1.0 - clamp01(dist)


def sheaf_gluing_score(matrix, window=12):
    '''
    Approximate continuation sheaf gluing.

    Each local window acts like a local persistence section.

    The system strengthens if:
    neighboring local sections overlap coherently.
    '''
    sections = []

    for i in range(0, len(matrix) - window, window):
        section = np.mean(matrix[i:i+window], axis=0)
        sections.append(section)

    overlaps = []

    for i in range(len(sections) - 1):
        overlaps.append(
            local_section_overlap(
                sections[i],
                sections[i+1]
            )
        )

    return float(np.mean(overlaps)) if overlaps else 0.0


def random_cover_shuffle(matrix):
    '''
    Hostile site/cover attack:
    destroy locality while preserving raw values.
    '''
    idx = np.arange(len(matrix))
    rng.shuffle(idx)
    return matrix[idx]


def continuation_breaks(matrix, threshold=0.55):
    '''
    Approximate non-gluing obstruction rate.

    Low overlap = continuation fracture.
    '''
    sections = []

    window = 10

    for i in range(0, len(matrix) - window, window):
        section = np.mean(matrix[i:i+window], axis=0)
        sections.append(section)

    failures = 0

    for i in range(len(sections) - 1):
        overlap = local_section_overlap(
            sections[i],
            sections[i+1]
        )

        if overlap < threshold:
            failures += 1

    return failures / max(1, len(sections) - 1)


def evaluate(name, matrix):
    glue = sheaf_gluing_score(matrix)

    shuffled = random_cover_shuffle(matrix)

    shuffled_glue = sheaf_gluing_score(shuffled)

    obstruction = continuation_breaks(matrix)

    if glue > shuffled_glue + 0.15 and obstruction < 0.25:
        result = "GLOBAL_CONTINUATION_SUPPORTED"
    elif glue > shuffled_glue:
        result = "PARTIAL_CONTINUATION"
    else:
        result = "NO_CONTINUATION_ADVANTAGE"

    return {
        "system": name,
        "gluing_score": round(glue, 6),
        "shuffled_gluing": round(shuffled_glue, 6),
        "obstruction_rate": round(obstruction, 6),
        "result": result,
    }


def main():
    rows = []

    structured = make_structured_system()
    random_system = make_random_system()
    fragmented = make_fragmented_system()

    rows.append(evaluate("structured_continuity", structured))
    rows.append(evaluate("random_system", random_system))
    rows.append(evaluate("fragmented_system", fragmented))

    strong = sum(
        1 for r in rows
        if r["result"] == "GLOBAL_CONTINUATION_SUPPORTED"
    )

    if strong >= 1 and rows[0]["result"] == "GLOBAL_CONTINUATION_SUPPORTED":
        final = "PRE_COORDINATE_CONTINUATION_STRUCTURE_SUPPORTED"
    elif rows[0]["result"] != "NO_CONTINUATION_ADVANTAGE":
        final = "PARTIAL_PRE_COORDINATE_CONTINUATION"
    else:
        final = "PRE_COORDINATE_CONTINUATION_NOT_DIFFERENTIATED"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# GV Continuation Sheaf Result",
        "",
        "## Purpose",
        "",
        "Test whether local persistence structures glue into global continuation structure.",
        "",
        "## Final Result",
        "",
        f"`{final}`",
        "",
        "## Results",
        "",
        "| System | Gluing Score | Shuffled Gluing | Obstruction Rate | Result |",
        "|---|---:|---:|---:|---|",
    ]

    for r in rows:
        lines.append(
            f"| {r['system']} | {r['gluing_score']} | "
            f"{r['shuffled_gluing']} | {r['obstruction_rate']} | "
            f"{r['result']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "This is an approximate continuation-sheaf style test.",
        "",
        "The question is whether local persistence structures can globally cohere.",
        "",
        "Random cover shuffling acts as a hostile locality-destruction attack.",
        "",
        "If structured continuity survives gluing better than random organization,",
        "GV strengthens at the pre-coordinate level.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "final": final,
        "rows": rows,
    })

    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
