import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_geometry_audit/RECOVERABILITY_GEOMETRY_AUDIT.md")
OUT_CSV = Path("reports/gv_geometry_audit/recoverability_geometry_audit.csv")

SOURCES = [
    {
        "name": "dominant_axis",
        "path": Path("reports/gv_dominant_axis/dominant_axis_cases.csv"),
        "gv_col": "gv",
        "feature_cols": [
            "recovery_strength",
            "persistence",
            "directional_degradation",
            "volatility_penalty",
            "recovery_time",
            "hysteresis",
            "future_sensitivity",
        ],
        "invert_cols": [
            "volatility_penalty",
            "recovery_time",
            "hysteresis",
            "future_sensitivity",
        ],
    },
    {
        "name": "panarchy",
        "path": Path("reports/gv_panarchy/panarchy_adversarial_cases.csv"),
        "gv_col": "global_gv",
        "feature_cols": [
            "local_recovery_strength",
            "local_persistence",
            "local_directional",
            "local_volatility",
            "global_resource",
            "global_hysteresis",
            "coupling_gap",
        ],
        "invert_cols": [
            "local_volatility",
            "global_hysteresis",
            "coupling_gap",
        ],
    },
    {
        "name": "hypergraph",
        "path": Path("reports/gv_hypergraph/hypergraph_manifold_cases.csv"),
        "gv_col": "combined_gv",
        "feature_cols": [
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
        ],
        "invert_cols": [
            "local_volatility",
            "hidden_global_strain",
            "fragmentation",
            "local_global_gap",
        ],
    },
]


def corr(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)

    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0

    return float(np.corrcoef(a, b)[0, 1])


def load_source(src):
    rows = list(csv.DictReader(src["path"].open()))

    matrix = []
    gv = []

    for row in rows:
        vec = []

        for col in src["feature_cols"]:
            v = float(row[col])
            if col in src["invert_cols"]:
                v = 1.0 - abs(v)
            vec.append(v)

        matrix.append(vec)
        gv.append(float(row[src["gv_col"]]))

    return np.array(matrix, dtype=float), np.array(gv, dtype=float)


def pca(matrix):
    x = matrix - matrix.mean(axis=0)
    u, s, vt = np.linalg.svd(x, full_matrices=False)

    variance = s ** 2
    explained = variance / variance.sum()

    scores = x @ vt.T

    return explained, scores, s


def random_projection_baseline(matrix, gv, trials=500, seed=42):
    rng = np.random.default_rng(seed)

    x = matrix - matrix.mean(axis=0)

    best = 0.0
    avg = 0.0

    vals = []

    for _ in range(trials):
        w = rng.normal(0, 1, size=x.shape[1])
        w = w / (np.linalg.norm(w) or 1.0)
        proj = x @ w
        c = abs(corr(gv, proj))
        vals.append(c)
        best = max(best, c)

    avg = float(np.mean(vals))

    return avg, best


def audit_source(src):
    matrix, gv = load_source(src)
    explained, scores, s = pca(matrix)

    pc1 = scores[:, 0]

    if corr(gv, pc1) < 0:
        pc1 = -pc1

    pc1_corr = corr(gv, pc1)

    residual_power = 1.0 - float(explained[0])

    pc2_corr = abs(corr(gv, scores[:, 1])) if scores.shape[1] > 1 else 0.0
    pc3_corr = abs(corr(gv, scores[:, 2])) if scores.shape[1] > 2 else 0.0

    eig_ratio = float(s[0] / s[1]) if len(s) > 1 and s[1] != 0 else float("inf")

    random_avg, random_best = random_projection_baseline(matrix, gv)

    if (
        explained[0] >= 0.75
        and abs(pc1_corr) >= 0.85
        and abs(pc1_corr) > random_avg + 0.15
    ):
        result = "GEOMETRY_SUPPORTS_DOMINANT_AXIS"
    elif abs(pc1_corr) <= random_best + 0.02:
        result = "GV_NOT_DISTINCT_FROM_RANDOM_PROJECTION"
    else:
        result = "GEOMETRY_PARTIAL_OR_INCONCLUSIVE"

    return {
        "source": src["name"],
        "rows": matrix.shape[0],
        "features": matrix.shape[1],
        "pc1_explained": round(float(explained[0]), 6),
        "pc2_explained": round(float(explained[1]), 6) if len(explained) > 1 else 0.0,
        "pc3_explained": round(float(explained[2]), 6) if len(explained) > 2 else 0.0,
        "residual_after_pc1": round(float(residual_power), 6),
        "pc1_gv_corr": round(float(pc1_corr), 6),
        "pc2_gv_corr_abs": round(float(pc2_corr), 6),
        "pc3_gv_corr_abs": round(float(pc3_corr), 6),
        "eigen_ratio_1_to_2": round(float(eig_ratio), 6),
        "random_projection_avg_corr": round(float(random_avg), 6),
        "random_projection_best_corr": round(float(random_best), 6),
        "result": result,
    }


def main():
    results = []

    for src in SOURCES:
        if not src["path"].exists():
            print(f"SKIP missing {src['path']}")
            continue

        results.append(audit_source(src))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    lines = [
        "# GV Recoverability Geometry Audit",
        "",
        "## Purpose",
        "",
        "Test whether GV is seeing a real dominant recoverability geometry or merely threading selected metrics.",
        "",
        "## Results",
        "",
        "| Source | PC1 Var | GV-PC1 Corr | Residual | Random Avg | Random Best | Result |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    for r in results:
        lines.append(
            f"| {r['source']} | {r['pc1_explained']} | {r['pc1_gv_corr']} | "
            f"{r['residual_after_pc1']} | {r['random_projection_avg_corr']} | "
            f"{r['random_projection_best_corr']} | {r['result']} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "If GV correlation is not meaningfully better than random projection, GV may be metric-threading.",
        "",
        "If PC1 dominates and GV aligns strongly beyond random projection, the geometry supports a dominant recoverability axis.",
        "",
        "## Scientific posture",
        "",
        "This audit is skeptical by design.",
        "",
        "It does not prove GV.",
        "",
        "It tests whether the geometry deserves continued attention.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(results)
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
