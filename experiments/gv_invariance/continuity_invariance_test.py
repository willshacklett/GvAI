import csv
from pathlib import Path
import numpy as np

from gvai.foundational_gv import ContinuityState, gv_foundation

SOURCE = Path("reports/gv_hypergraph/hypergraph_manifold_cases.csv")

OUT_MD = Path("reports/gv_invariance/CONTINUITY_INVARIANCE_RESULT.md")
OUT_CSV = Path("reports/gv_invariance/continuity_invariance_result.csv")

SEED = 42
TRIALS = 500

FEATURES = [
    "local_recovery",
    "local_persistence",
    "local_directional",
    "local_volatility",
    "resource",
    "hidden_global_strain",
    "fragmentation",
    "local_global_gap",
]

INVERT = {
    "local_volatility",
    "hidden_global_strain",
    "fragmentation",
    "local_global_gap",
}


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def load_rows():
    rows = list(csv.DictReader(SOURCE.open()))

    cases = []

    for r in rows:
        # Foundational GV uses continuity fields directly.
        recovery = float(r["resource"])
        persistence = 1.0 - abs(float(r["hidden_global_strain"]))
        directional = 1.0 - abs(float(r["local_global_gap"]))
        volatility = abs(float(r["fragmentation"]))

        gv = gv_foundation(ContinuityState(
            recovery=recovery,
            persistence=persistence,
            directional_integrity=directional,
            volatility=volatility,
        ))

        vec = []

        for col in FEATURES:
            v = float(r[col])
            if col in INVERT:
                v = 1.0 - abs(v)
            vec.append(clamp01(v))

        cases.append({
            "time": int(float(r["time"])),
            "features": vec,
            "gv": gv,
        })

    return cases


def rank_order(values):
    return np.argsort(np.argsort(values))


def spearman_like(a, b):
    ra = rank_order(a)
    rb = rank_order(b)

    if np.std(ra) == 0 or np.std(rb) == 0:
        return 0.0

    return float(np.corrcoef(ra, rb)[0, 1])


def pairwise_violation_rate(base, transformed):
    violations = 0
    total = 0

    n = len(base)

    for i in range(n):
        for j in range(i + 1, n):
            base_cmp = base[i] - base[j]
            trans_cmp = transformed[i] - transformed[j]

            if abs(base_cmp) < 1e-9:
                continue

            total += 1

            if base_cmp * trans_cmp < 0:
                violations += 1

    return violations / total if total else 0.0


def transform_features(matrix, rng, mode):
    x = np.array(matrix, dtype=float)

    if mode == "scale":
        scales = rng.uniform(0.5, 2.5, size=x.shape[1])
        return x * scales

    if mode == "monotonic":
        # Strict monotonic transform per feature.
        return np.sqrt(np.clip(x, 0, None))

    if mode == "noise":
        return np.clip(x + rng.normal(0, 0.03, size=x.shape), 0, 1)

    if mode == "rotation":
        centered = x - x.mean(axis=0)
        q, _ = np.linalg.qr(rng.normal(size=(x.shape[1], x.shape[1])))
        rotated = centered @ q
        # rescale back to [0,1] per column
        mn = rotated.min(axis=0)
        mx = rotated.max(axis=0)
        return (rotated - mn) / np.where(mx - mn == 0, 1, mx - mn)

    raise ValueError(mode)


def gv_from_transformed_features(row):
    # Treat first four transformed continuity-like axes as generic evidence.
    f = row

    return gv_foundation(ContinuityState(
        recovery=clamp01(f[0]),
        persistence=clamp01(f[1]),
        directional_integrity=clamp01(f[2]),
        volatility=clamp01(1.0 - f[3]),
    ))


def random_projection_scores(matrix, rng, trials=TRIALS):
    x = np.array(matrix, dtype=float)
    scores = []

    for _ in range(trials):
        w = rng.normal(0, 1, size=x.shape[1])
        w = w / (np.linalg.norm(w) or 1.0)

        proj = x @ w
        # normalize projection to [0,1]
        proj = (proj - proj.min()) / (proj.max() - proj.min() or 1.0)
        scores.append(proj)

    return scores


def main():
    rng = np.random.default_rng(SEED)

    cases = load_rows()

    matrix = np.array([c["features"] for c in cases], dtype=float)
    gv_base = np.array([c["gv"] for c in cases], dtype=float)

    modes = ["scale", "monotonic", "noise", "rotation"]

    result_rows = []

    for mode in modes:
        transformed = transform_features(matrix, rng, mode)

        gv_transformed = np.array([
            gv_from_transformed_features(row)
            for row in transformed
        ])

        gv_rank_stability = spearman_like(gv_base, gv_transformed)
        gv_violation_rate = pairwise_violation_rate(gv_base, gv_transformed)

        random_stabilities = []
        random_violations = []

        base_randoms = random_projection_scores(matrix, rng, trials=TRIALS)
        trans_randoms = random_projection_scores(transformed, rng, trials=TRIALS)

        for base_proj, trans_proj in zip(base_randoms, trans_randoms):
            random_stabilities.append(spearman_like(base_proj, trans_proj))
            random_violations.append(pairwise_violation_rate(base_proj, trans_proj))

        random_avg_stability = float(np.mean(random_stabilities))
        random_p95_stability = float(np.percentile(random_stabilities, 95))
        random_avg_violation = float(np.mean(random_violations))
        random_p05_violation = float(np.percentile(random_violations, 5))

        if (
            gv_rank_stability > random_p95_stability
            and gv_violation_rate < random_p05_violation
        ):
            mode_result = "GV_INVARIANT_BEYOND_RANDOM"
        elif gv_rank_stability > random_avg_stability:
            mode_result = "GV_ABOVE_AVERAGE_INVARIANCE"
        else:
            mode_result = "GV_NOT_INVARIANT_BEYOND_RANDOM"

        result_rows.append({
            "mode": mode,
            "gv_rank_stability": round(gv_rank_stability, 6),
            "gv_violation_rate": round(gv_violation_rate, 6),
            "random_avg_stability": round(random_avg_stability, 6),
            "random_p95_stability": round(random_p95_stability, 6),
            "random_avg_violation": round(random_avg_violation, 6),
            "random_p05_violation": round(random_p05_violation, 6),
            "result": mode_result,
        })

    wins = sum(1 for r in result_rows if r["result"] == "GV_INVARIANT_BEYOND_RANDOM")
    partial = sum(1 for r in result_rows if r["result"] == "GV_ABOVE_AVERAGE_INVARIANCE")

    if wins >= 2:
        final = "GV_SHOWS_CONTINUITY_INVARIANCE"
    elif wins + partial >= 2:
        final = "GV_SHOWS_PARTIAL_CONTINUITY_INVARIANCE"
    else:
        final = "GV_FAILS_CONTINUITY_INVARIANCE"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(result_rows[0].keys()))
        writer.writeheader()
        writer.writerows(result_rows)

    lines = [
        "# GV Continuity Invariance Result",
        "",
        "## Purpose",
        "",
        "Test whether GV preserves continuity ordering under harmless representation changes better than random projections.",
        "",
        f"## Final Result",
        "",
        f"`{final}`",
        "",
        "## Transformation Results",
        "",
        "| Mode | GV Rank Stability | GV Violation Rate | Random Avg Stability | Random P95 Stability | Random Avg Violation | Random P05 Violation | Result |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]

    for r in result_rows:
        lines.append(
            f"| {r['mode']} | {r['gv_rank_stability']} | {r['gv_violation_rate']} | "
            f"{r['random_avg_stability']} | {r['random_p95_stability']} | "
            f"{r['random_avg_violation']} | {r['random_p05_violation']} | {r['result']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "Random projections can correlate with low-dimensional data.",
        "",
        "This test asks a harder question: does GV preserve continuity ordering under transformations that should not change meaning?",
        "",
        "If GV fails here, it is not yet behaving like a foundational invariant.",
        "",
        "If GV survives here, it earns a stronger claim than PC1 correlation.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({"final": final, "rows": result_rows})
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
