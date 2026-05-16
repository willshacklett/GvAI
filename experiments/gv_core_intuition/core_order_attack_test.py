import csv
from pathlib import Path
import numpy as np

SOURCE = Path("reports/gv_hypergraph/hypergraph_manifold_cases.csv")

OUT_MD = Path("reports/gv_core_intuition/CORE_ORDER_ATTACK_RESULT.md")
OUT_CSV = Path("reports/gv_core_intuition/core_order_attack_result.csv")

SEED = 42

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


def dominance_order(matrix):
    n = matrix.shape[0]
    orders = {}

    for i in range(n):
        for j in range(i + 1, n):
            better = int(np.sum(matrix[i] > matrix[j]))
            worse = int(np.sum(matrix[i] < matrix[j]))

            if better > worse:
                orders[(i, j)] = 1
            elif worse > better:
                orders[(i, j)] = -1
            else:
                orders[(i, j)] = 0

    return orders


def cycle_rate(matrix, sample_limit=25000):
    rng = np.random.default_rng(SEED)
    n = matrix.shape[0]

    if n < 3:
        return 0.0

    order = dominance_order(matrix)

    cycles = 0
    checked = 0

    for _ in range(sample_limit):
        a, b, c = rng.choice(n, size=3, replace=False)

        pairs = [
            tuple(sorted((a, b))),
            tuple(sorted((b, c))),
            tuple(sorted((c, a))),
        ]

        def rel(x, y):
            key = tuple(sorted((x, y)))
            v = order.get(key, 0)
            if key != (x, y):
                v = -v
            return v

        ab = rel(a, b)
        bc = rel(b, c)
        ca = rel(c, a)

        if ab == 1 and bc == 1 and ca == 1:
            cycles += 1
        elif ab == -1 and bc == -1 and ca == -1:
            cycles += 1

        checked += 1

    return cycles / checked if checked else 0.0


def incomparability_rate(matrix):
    order = dominance_order(matrix)
    total = len(order)
    ties = sum(1 for v in order.values() if v == 0)
    return ties / total if total else 0.0


def transform(matrix, mode):
    rng = np.random.default_rng(SEED + len(mode))
    x = np.array(matrix, dtype=float)

    if mode == "baseline":
        return x

    if mode == "scale":
        return x * rng.uniform(0.25, 4.0, size=x.shape[1])

    if mode == "monotonic":
        return np.sqrt(np.clip(x, 0, None))

    if mode == "noise":
        return np.clip(x + rng.normal(0, 0.035, size=x.shape), 0, 1)

    if mode == "rotation":
        centered = x - x.mean(axis=0)
        q, _ = np.linalg.qr(rng.normal(size=(x.shape[1], x.shape[1])))
        y = centered @ q
        mn = y.min(axis=0)
        mx = y.max(axis=0)
        return (y - mn) / np.where(mx - mn == 0, 1, mx - mn)

    if mode == "condorcet_attack":
        y = np.array(x, copy=True)
        # Adversarially mix continuity dimensions to induce voting conflict.
        y[:, [0, 1, 2]] = y[:, [1, 2, 0]]
        y[:, 3] = 1.0 - y[:, 3]
        y[:, 6] = 1.0 - y[:, 6]
        return np.clip(y, 0, 1)

    if mode == "incomparability_attack":
        y = np.array(x, copy=True)
        # Force half dimensions to oppose the other half.
        half = y.shape[1] // 2
        y[:, half:] = 1.0 - y[:, half:]
        return np.clip(y, 0, 1)

    raise ValueError(mode)


def order_survival(base, other):
    kept = 0
    flipped = 0
    total = 0

    for k, v in base.items():
        if v == 0:
            continue

        ov = other.get(k, 0)
        total += 1

        if ov == v:
            kept += 1
        elif ov == -v:
            flipped += 1

    return {
        "survival": kept / total if total else 0.0,
        "flip_rate": flipped / total if total else 0.0,
    }


def main():
    matrix = load_matrix()
    base_order = dominance_order(matrix)

    modes = [
        "baseline",
        "scale",
        "monotonic",
        "noise",
        "rotation",
        "condorcet_attack",
        "incomparability_attack",
    ]

    rows = []

    for mode in modes:
        m = transform(matrix, mode)
        o = dominance_order(m)
        survival = order_survival(base_order, o)

        rows.append({
            "mode": mode,
            "order_survival": round(survival["survival"], 6),
            "flip_rate": round(survival["flip_rate"], 6),
            "cycle_rate": round(cycle_rate(m), 6),
            "incomparability_rate": round(incomparability_rate(m), 6),
        })

    # Core read:
    # Preserve honest distinction between harmless transforms and hostile attacks.
    harmless = [r for r in rows if r["mode"] in ["scale", "monotonic", "noise"]]
    hostile = [r for r in rows if r["mode"] in ["rotation", "condorcet_attack", "incomparability_attack"]]

    harmless_survives = all(r["order_survival"] >= 0.80 for r in harmless)
    hostile_breaks = any(r["flip_rate"] >= 0.25 or r["incomparability_rate"] >= 0.20 for r in hostile)

    if harmless_survives and hostile_breaks:
        final = "CORE_CONTINUITY_SURVIVES_HARMLESS_TRANSFORMS_BREAKS_UNDER_HOSTILE_ATTACK"
    elif harmless_survives:
        final = "CORE_CONTINUITY_ORDER_SURVIVES"
    else:
        final = "CORE_CONTINUITY_ORDER_FAILS"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# GV Core Order Attack Result",
        "",
        "## Purpose",
        "",
        "Keep the core intuition: persistent existence requires continuity.",
        "",
        "Test that intuition as a non-weighted order relation, then attack it.",
        "",
        "## Final Result",
        "",
        f"`{final}`",
        "",
        "## Results",
        "",
        "| Mode | Order Survival | Flip Rate | Cycle Rate | Incomparability Rate |",
        "|---|---:|---:|---:|---:|",
    ]

    for r in rows:
        lines.append(
            f"| {r['mode']} | {r['order_survival']} | {r['flip_rate']} | "
            f"{r['cycle_rate']} | {r['incomparability_rate']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "GV is not tuned here.",
        "",
        "The test preserves the core intuition by treating continuity as relational order.",
        "",
        "Harmless transforms should preserve order.",
        "",
        "Hostile transforms are allowed to break it.",
        "",
        "A real foundation should not be invincible; it should show where it holds and where it fractures.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"final": final, "rows": rows})
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
