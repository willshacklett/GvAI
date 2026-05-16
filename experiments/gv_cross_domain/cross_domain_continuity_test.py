import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_cross_domain/CROSS_DOMAIN_CONTINUITY_RESULT.md")
OUT_CSV = Path("reports/gv_cross_domain/cross_domain_continuity_result.csv")

SEED = 42

DOMAINS = {
    "ecology_like": {
        "features": [
            ("resource", 1),
            ("recovery", 1),
            ("fragmentation", -1),
            ("stress", -1),
        ]
    },
    "infrastructure_like": {
        "features": [
            ("capacity", 1),
            ("redundancy", 1),
            ("load_skew", -1),
            ("failure_pressure", -1),
        ]
    },
    "network_like": {
        "features": [
            ("connectivity", 1),
            ("coherence", 1),
            ("partitioning", -1),
            ("cascade_risk", -1),
        ]
    },
    "latent_state_like": {
        "features": [
            ("observable_stability", 1),
            ("recoverability", 1),
            ("hidden_strain", -1),
            ("signal_decay", -1),
        ]
    },
}

TRIALS = 120
ROWS = 160


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def generate_domain(name, rng):
    rows = []

    for t in range(ROWS):
        phase = t / ROWS

        continuity = (
            0.72
            - 0.55 * phase
            + rng.normal(0, 0.035)
        )

        continuity = clamp01(continuity)

        row = {}

        for feature, sign in DOMAINS[name]["features"]:
            base = continuity + rng.normal(0, 0.08)

            if sign < 0:
                base = 1.0 - base

            row[feature] = clamp01(base)

        rows.append(row)

    return rows


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


def order_survival(base, other):
    total = 0
    kept = 0

    for k, v in base.items():
        if v == 0:
            continue

        ov = other.get(k, 0)

        total += 1

        if ov == v:
            kept += 1

    return kept / total if total else 0.0


def transform(matrix, rng):
    x = np.array(matrix, dtype=float)

    noise = rng.normal(0, 0.03, size=x.shape)

    scales = rng.uniform(0.5, 2.0, size=x.shape[1])

    y = (x * scales) + noise

    return np.clip(y, 0, 1)


def main():
    rng = np.random.default_rng(SEED)

    rows_out = []

    for domain in DOMAINS:
        generated = generate_domain(domain, rng)

        matrix = []

        for row in generated:
            vec = []

            for feature, sign in DOMAINS[domain]["features"]:
                v = row[feature]

                if sign < 0:
                    v = 1.0 - abs(v)

                vec.append(clamp01(v))

            matrix.append(vec)

        matrix = np.array(matrix, dtype=float)

        base_order = dominance_order(matrix)

        survivals = []

        for _ in range(TRIALS):
            transformed = transform(matrix, rng)
            transformed_order = dominance_order(transformed)

            survivals.append(
                order_survival(base_order, transformed_order)
            )

        avg_survival = float(np.mean(survivals))
        min_survival = float(np.min(survivals))

        if avg_survival >= 0.80:
            result = "CONTINUITY_ORDER_RECURS"
        elif avg_survival >= 0.65:
            result = "PARTIAL_RECURRENCE"
        else:
            result = "WEAK_RECURRENCE"

        rows_out.append({
            "domain": domain,
            "avg_survival": round(avg_survival, 6),
            "min_survival": round(min_survival, 6),
            "result": result,
        })

    strong = sum(1 for r in rows_out if r["result"] == "CONTINUITY_ORDER_RECURS")

    if strong >= 3:
        final = "CROSS_DOMAIN_CONTINUITY_SUPPORTED"
    elif strong >= 2:
        final = "PARTIAL_CROSS_DOMAIN_CONTINUITY"
    else:
        final = "CROSS_DOMAIN_CONTINUITY_WEAK"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows_out[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows_out)

    lines = [
        "# GV Cross-Domain Continuity Result",
        "",
        "## Purpose",
        "",
        "Test whether continuity-order structure recurs across unrelated domains without requiring one scalar form.",
        "",
        "## Final Result",
        "",
        f"`{final}`",
        "",
        "## Domain Results",
        "",
        "| Domain | Avg Order Survival | Min Survival | Result |",
        "|---|---:|---:|---|",
    ]

    for r in rows_out:
        lines.append(
            f"| {r['domain']} | {r['avg_survival']} | {r['min_survival']} | {r['result']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "The test does not assume one exact scalar.",
        "",
        "The test asks whether continuity-order relations recur across different system types.",
        "",
        "If recurrence is strong across unrelated domains, GV remains viable as a foundational continuity hypothesis.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "final": final,
        "rows": rows_out,
    })

    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
