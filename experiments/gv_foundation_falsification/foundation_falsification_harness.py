import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_foundation_falsification/FOUNDATION_FALSIFICATION_RESULT.md")
OUT_CSV = Path("reports/gv_foundation_falsification/foundation_falsification_result.csv")

SEED = 42
ROWS = 180

rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def dominance_order(matrix):
    n = matrix.shape[0]
    order = {}

    for i in range(n):
        for j in range(i + 1, n):
            better = int(np.sum(matrix[i] > matrix[j]))
            worse = int(np.sum(matrix[i] < matrix[j]))

            if better > worse:
                order[(i, j)] = 1
            elif worse > better:
                order[(i, j)] = -1
            else:
                order[(i, j)] = 0

    return order


def incomparability_rate(order):
    total = len(order)
    ties = sum(1 for v in order.values() if v == 0)
    return ties / total if total else 0.0


def order_survival(base, other):
    kept = 0
    total = 0

    for k, v in base.items():
        if v == 0:
            continue

        total += 1

        if other.get(k, 0) == v:
            kept += 1

    return kept / total if total else 0.0


def make_continuity_system():
    rows = []

    for t in range(ROWS):
        phase = t / ROWS

        continuity = clamp01(
            0.82
            - 0.60 * phase
            + rng.normal(0, 0.04)
        )

        rows.append([
            continuity + rng.normal(0, 0.05),
            continuity + rng.normal(0, 0.05),
            continuity + rng.normal(0, 0.05),
            1.0 - continuity + rng.normal(0, 0.05),
        ])

    return np.clip(np.array(rows), 0, 1)


def make_random_system():
    return rng.uniform(0, 1, size=(ROWS, 4))


def make_local_global_deception():
    rows = []

    for t in range(ROWS):
        phase = t / ROWS

        local = clamp01(0.78 + rng.normal(0, 0.03))
        global_strain = clamp01(phase + rng.normal(0, 0.05))

        rows.append([
            local,
            local,
            1.0 - global_strain,
            global_strain,
        ])

    return np.clip(np.array(rows), 0, 1)


def rotate(matrix):
    centered = matrix - matrix.mean(axis=0)

    q, _ = np.linalg.qr(rng.normal(size=(matrix.shape[1], matrix.shape[1])))

    y = centered @ q

    mn = y.min(axis=0)
    mx = y.max(axis=0)

    return (y - mn) / np.where(mx - mn == 0, 1, mx - mn)


def main():
    rows_out = []

    # 1. Structured continuity system
    continuity_system = make_continuity_system()
    base_order = dominance_order(continuity_system)

    rotated = rotate(continuity_system)
    rotated_order = dominance_order(rotated)

    rows_out.append({
        "test": "structured_continuity_rotation",
        "metric": "order_survival",
        "value": round(order_survival(base_order, rotated_order), 6),
        "interpretation": "High survival suggests meaningful continuity structure.",
    })

    # 2. Random system
    random_system = make_random_system()
    random_order = dominance_order(random_system)

    rows_out.append({
        "test": "random_system",
        "metric": "incomparability_rate",
        "value": round(incomparability_rate(random_order), 6),
        "interpretation": "High incomparability weakens random continuity claims.",
    })

    # 3. Local/global deception
    deceptive = make_local_global_deception()
    deceptive_order = dominance_order(deceptive)

    rows_out.append({
        "test": "local_global_deception",
        "metric": "incomparability_rate",
        "value": round(incomparability_rate(deceptive_order), 6),
        "interpretation": "Global strain hidden behind local stability.",
    })

    # 4. Random rotation comparison
    random_rot = rotate(random_system)
    random_rot_order = dominance_order(random_rot)

    rows_out.append({
        "test": "random_rotation_survival",
        "metric": "order_survival",
        "value": round(order_survival(random_order, random_rot_order), 6),
        "interpretation": "If random survival equals structured survival, GV weakens.",
    })

    structured_survival = rows_out[0]["value"]
    random_survival = rows_out[3]["value"]

    if structured_survival > random_survival + 0.20:
        final = "FOUNDATION_CONTINUITY_STRUCTURE_DIFFERENTIATED"
    elif structured_survival > random_survival:
        final = "FOUNDATION_PARTIAL_DIFFERENTIATION"
    else:
        final = "FOUNDATION_NOT_DIFFERENTIATED"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["test", "metric", "value", "interpretation"],
        )
        writer.writeheader()
        writer.writerows(rows_out)

    lines = [
        "# GV Foundation Falsification Result",
        "",
        "## Purpose",
        "",
        "Pressure the GV foundation directly without rescue logic.",
        "",
        "## Final Result",
        "",
        f"`{final}`",
        "",
        "## Results",
        "",
        "| Test | Metric | Value | Interpretation |",
        "|---|---|---:|---|",
    ]

    for r in rows_out:
        lines.append(
            f"| {r['test']} | {r['metric']} | {r['value']} | {r['interpretation']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "This harness tests whether continuity structure differs meaningfully from random organization.",
        "",
        "If structured continuity repeatedly survives better than random continuity,",
        "the foundation strengthens.",
        "",
        "If random systems preserve continuity equally well,",
        "the foundation weakens.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "final": final,
        "structured_survival": structured_survival,
        "random_survival": random_survival,
    })

    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
