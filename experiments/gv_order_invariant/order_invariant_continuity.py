import csv
from pathlib import Path
import numpy as np

SOURCE = Path("reports/gv_hypergraph/hypergraph_manifold_cases.csv")

OUT_MD = Path("reports/gv_order_invariant/ORDER_INVARIANT_CONTINUITY_RESULT.md")
OUT_CSV = Path("reports/gv_order_invariant/order_invariant_continuity_result.csv")

SEED = 42
TRIALS = 300

# No tuned weights.
# Each feature contributes only by pairwise dominance direction.
FEATURES = [
    ("local_recovery", 1),
    ("local_persistence", 1),
    ("local_directional", 1),
    ("resource", 1),
    ("density", 1),
    ("avg_degree", 1),
    ("local_volatility", -1),
    ("hidden_global_strain", -1),
    ("fragmentation", -1),
    ("local_global_gap", -1),
]


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def load_matrix():
    rows = list(csv.DictReader(SOURCE.open()))

    matrix = []

    for r in rows:
        vec = []

        for col, direction in FEATURES:
            v = float(r[col])
            if direction < 0:
                v = 1.0 - abs(v)
            vec.append(clamp01(v))

        matrix.append(vec)

    return np.array(matrix, dtype=float)


def pairwise_continuity_order(matrix):
    '''
    Non-weighted order relation.

    For each pair i,j:
    i > j if i dominates j on more continuity dimensions.
    j > i if j dominates i on more continuity dimensions.
    tie otherwise.

    This avoids weighted scalar tuning.
    '''
    n = matrix.shape[0]

    orders = {}

    for i in range(n):
        for j in range(i + 1, n):
            better = np.sum(matrix[i] > matrix[j])
            worse = np.sum(matrix[i] < matrix[j])

            if better > worse:
                orders[(i, j)] = 1
            elif worse > better:
                orders[(i, j)] = -1
            else:
                orders[(i, j)] = 0

    return orders


def order_survival(base, transformed):
    kept = 0
    total = 0
    flips = 0

    for k, v in base.items():
        if v == 0:
            continue

        tv = transformed.get(k, 0)

        total += 1

        if tv == v:
            kept += 1
        elif tv == -v:
            flips += 1

    survival = kept / total if total else 0.0
    flip_rate = flips / total if total else 0.0

    return survival, flip_rate


def transform(matrix, rng, mode):
    x = np.array(matrix, dtype=float)

    if mode == "scale":
        scales = rng.uniform(0.25, 4.0, size=x.shape[1])
        y = x * scales
        return y

    if mode == "monotonic":
        return np.sqrt(np.clip(x, 0, None))

    if mode == "noise":
        return np.clip(x + rng.normal(0, 0.025, size=x.shape), 0, 1)

    if mode == "rotation":
        centered = x - x.mean(axis=0)
        q, _ = np.linalg.qr(rng.normal(size=(x.shape[1], x.shape[1])))
        y = centered @ q

        mn = y.min(axis=0)
        mx = y.max(axis=0)

        return (y - mn) / np.where(mx - mn == 0, 1, mx - mn)

    raise ValueError(mode)


def random_feature_permutation(matrix, rng):
    y = np.array(matrix, copy=True)

    for col in range(y.shape[1]):
        rng.shuffle(y[:, col])

    return y


def main():
    rng = np.random.default_rng(SEED)

    matrix = load_matrix()

    base_order = pairwise_continuity_order(matrix)

    modes = ["scale", "monotonic", "noise", "rotation"]

    rows = []

    for mode in modes:
        transformed = transform(matrix, rng, mode)
        transformed_order = pairwise_continuity_order(transformed)

        survival, flip_rate = order_survival(base_order, transformed_order)

        null_survivals = []
        null_flips = []

        for _ in range(TRIALS):
            null_matrix = random_feature_permutation(matrix, rng)
            null_order = pairwise_continuity_order(null_matrix)
            ns, nf = order_survival(base_order, null_order)
            null_survivals.append(ns)
            null_flips.append(nf)

        null_avg = float(np.mean(null_survivals))
        null_p95 = float(np.percentile(null_survivals, 95))
        null_flip_avg = float(np.mean(null_flips))
        null_flip_p05 = float(np.percentile(null_flips, 5))

        if survival > null_p95 and flip_rate < null_flip_p05:
            result = "ORDER_INVARIANT_BEYOND_NULL"
        elif survival > null_avg:
            result = "ORDER_INVARIANT_ABOVE_NULL_AVERAGE"
        else:
            result = "ORDER_INVARIANT_FAILS"

        rows.append({
            "mode": mode,
            "order_survival": round(survival, 6),
            "flip_rate": round(flip_rate, 6),
            "null_avg_survival": round(null_avg, 6),
            "null_p95_survival": round(null_p95, 6),
            "null_avg_flip": round(null_flip_avg, 6),
            "null_p05_flip": round(null_flip_p05, 6),
            "result": result,
        })

    wins = sum(1 for r in rows if r["result"] == "ORDER_INVARIANT_BEYOND_NULL")
    partial = sum(1 for r in rows if r["result"] == "ORDER_INVARIANT_ABOVE_NULL_AVERAGE")

    if wins >= 3:
        final = "GV_ORDER_INVARIANT_SURVIVES"
    elif wins + partial >= 3:
        final = "GV_ORDER_INVARIANT_PARTIAL"
    else:
        final = "GV_ORDER_INVARIANT_FAILS"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# GV Order-Invariant Continuity Result",
        "",
        "## Purpose",
        "",
        "Test GV without tuned scalar weights.",
        "",
        "Instead of optimizing an equation, this measures whether pairwise continuity order survives transformations.",
        "",
        "## Final Result",
        "",
        f"`{final}`",
        "",
        "## Results",
        "",
        "| Mode | Order Survival | Flip Rate | Null Avg Survival | Null P95 Survival | Null Avg Flip | Null P05 Flip | Result |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]

    for r in rows:
        lines.append(
            f"| {r['mode']} | {r['order_survival']} | {r['flip_rate']} | "
            f"{r['null_avg_survival']} | {r['null_p95_survival']} | "
            f"{r['null_avg_flip']} | {r['null_p05_flip']} | {r['result']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "This test removes weighted tuning.",
        "",
        "GV is tested as a preserved continuity order relation.",
        "",
        "If this survives, GV becomes less arbitrary than a scalar projection.",
        "",
        "If this fails, the current continuity relation is not yet invariant.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"final": final, "rows": rows})
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
