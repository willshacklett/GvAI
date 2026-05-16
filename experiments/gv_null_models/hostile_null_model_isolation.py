import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_null_models/HOSTILE_NULL_MODEL_RESULT.md")
OUT_CSV = Path("reports/gv_null_models/hostile_null_model_result.csv")

SOURCE = Path("reports/gv_hypergraph/hypergraph_manifold_cases.csv")

FEATURES = [
    "local_recovery",
    "local_persistence",
    "local_directional",
    "local_volatility",
    "resource",
    "hidden_global_strain",
    "density",
    "fragmentation",
    "avg_degree",
    "local_global_gap",
]

INVERT = {
    "local_volatility",
    "hidden_global_strain",
    "fragmentation",
    "local_global_gap",
}

GV_COL = "combined_gv"

SEED = 42
TRIALS = 2000


def corr(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)

    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0

    return float(np.corrcoef(a, b)[0, 1])


def load_data():
    rows = list(csv.DictReader(SOURCE.open()))

    matrix = []
    gv = []

    for row in rows:
        vec = []
        for col in FEATURES:
            v = float(row[col])
            if col in INVERT:
                v = 1.0 - abs(v)
            vec.append(v)

        matrix.append(vec)
        gv.append(float(row[GV_COL]))

    return np.array(matrix, dtype=float), np.array(gv, dtype=float)


def pca_pc1(matrix):
    x = matrix - matrix.mean(axis=0)
    u, s, vt = np.linalg.svd(x, full_matrices=False)
    pc1 = x @ vt[0]

    explained = float((s[0] ** 2) / np.sum(s ** 2))

    return pc1, explained


def random_projection_scores(matrix, target, trials=TRIALS):
    rng = np.random.default_rng(SEED)
    x = matrix - matrix.mean(axis=0)

    scores = []

    for _ in range(trials):
        w = rng.normal(0, 1, size=x.shape[1])
        w = w / (np.linalg.norm(w) or 1.0)

        proj = x @ w
        scores.append(abs(corr(target, proj)))

    return np.array(scores, dtype=float)


def shuffled_target_scores(matrix, target, trials=TRIALS):
    rng = np.random.default_rng(SEED + 1)

    scores = []

    for _ in range(trials):
        shuffled = np.array(target, copy=True)
        rng.shuffle(shuffled)

        pc1, _ = pca_pc1(matrix)
        scores.append(abs(corr(shuffled, pc1)))

    return np.array(scores, dtype=float)


def rotated_feature_test(matrix, target):
    rng = np.random.default_rng(SEED + 2)

    x = matrix - matrix.mean(axis=0)

    q, _ = np.linalg.qr(rng.normal(size=(x.shape[1], x.shape[1])))
    rotated = x @ q

    pc1, explained = pca_pc1(rotated)

    return abs(corr(target, pc1)), explained


def noisy_orthogonal_test(matrix, target, noise_level):
    rng = np.random.default_rng(SEED + int(noise_level * 1000))

    x = matrix - matrix.mean(axis=0)
    noise = rng.normal(0, noise_level, size=x.shape)

    noisy = x + noise

    pc1, explained = pca_pc1(noisy)

    return abs(corr(target, pc1)), explained


def percentile_rank(value, distribution):
    return float(np.mean(distribution <= value))


def main():
    matrix, gv = load_data()

    pc1, pc1_explained = pca_pc1(matrix)

    if corr(gv, pc1) < 0:
        pc1 = -pc1

    gv_pc1_corr = abs(corr(gv, pc1))

    random_scores = random_projection_scores(matrix, gv)
    shuffled_scores = shuffled_target_scores(matrix, gv)

    rotated_corr, rotated_explained = rotated_feature_test(matrix, gv)

    noise_tests = []

    for noise in [0.05, 0.10, 0.25, 0.50]:
        c, e = noisy_orthogonal_test(matrix, gv, noise)
        noise_tests.append({
            "noise": noise,
            "corr": c,
            "pc1_explained": e,
        })

    random_avg = float(np.mean(random_scores))
    random_best = float(np.max(random_scores))
    random_p95 = float(np.percentile(random_scores, 95))

    shuffled_avg = float(np.mean(shuffled_scores))
    shuffled_best = float(np.max(shuffled_scores))

    gv_percentile = percentile_rank(gv_pc1_corr, random_scores)

    # Hard skeptical result
    if gv_pc1_corr > random_p95 and gv_percentile >= 0.95:
        result = "GV_OUTPERFORMS_HOSTILE_RANDOM_PROJECTIONS"
    elif gv_pc1_corr > random_avg:
        result = "GV_ABOVE_AVERAGE_BUT_NOT_PRIVILEGED"
    else:
        result = "GV_NOT_DISTINCT_FROM_NULL_MODELS"

    rows = [{
        "source": str(SOURCE),
        "rows": matrix.shape[0],
        "features": matrix.shape[1],
        "pc1_explained": round(pc1_explained, 6),
        "gv_pc1_corr": round(gv_pc1_corr, 6),
        "random_avg_corr": round(random_avg, 6),
        "random_p95_corr": round(random_p95, 6),
        "random_best_corr": round(random_best, 6),
        "gv_percentile_vs_random": round(gv_percentile, 6),
        "shuffled_avg_corr": round(shuffled_avg, 6),
        "shuffled_best_corr": round(shuffled_best, 6),
        "rotated_corr": round(rotated_corr, 6),
        "rotated_pc1_explained": round(rotated_explained, 6),
        "result": result,
    }]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    noise_lines = "\n".join(
        f"| {n['noise']} | {round(n['corr'], 6)} | {round(n['pc1_explained'], 6)} |"
        for n in noise_tests
    )

    OUT_MD.write_text(f'''# GV Hostile Null-Model Isolation Result

## Purpose

Test whether GV is mathematically privileged or merely one of many projections on compressible data.

## Result

`{result}`

## Main audit

| Metric | Value |
|---|---:|
| PC1 explained variance | {round(pc1_explained, 6)} |
| GV correlation with PC1 | {round(gv_pc1_corr, 6)} |
| random projection average corr | {round(random_avg, 6)} |
| random projection p95 corr | {round(random_p95, 6)} |
| random projection best corr | {round(random_best, 6)} |
| GV percentile vs random projections | {round(gv_percentile, 6)} |
| shuffled target average corr | {round(shuffled_avg, 6)} |
| shuffled target best corr | {round(shuffled_best, 6)} |
| rotated feature corr | {round(rotated_corr, 6)} |
| rotated PC1 explained variance | {round(rotated_explained, 6)} |

## Noise tests

| Orthogonal noise level | GV-PC1 corr after noise | PC1 explained |
|---:|---:|---:|
{noise_lines}

## Interpretation

If GV does not beat random projections, it is not yet mathematically privileged.

If GV beats random projections under rotation and noise, it earns stronger attention.

## Scientific line

This test gives GV a fair chance without assuming it is true.

It does not settle metaphysics.

It tests whether the proposed continuity scalar survives hostile null models.
''', encoding="utf-8")

    print(rows[0])
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()\n