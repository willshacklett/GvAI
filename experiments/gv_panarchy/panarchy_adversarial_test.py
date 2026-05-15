import csv
from pathlib import Path
import numpy as np

from gvai.universal_scalar import GVEvidence, gv_scalar

OUT_CSV = Path("reports/gv_panarchy/panarchy_adversarial_cases.csv")
OUT_MD = Path("reports/gv_panarchy/PANARCHY_ADVERSARIAL_RESULT.md")

STEPS = 120
MODULES = 5
SEED = 42


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def pca_first_component(matrix):
    x = np.array(matrix, dtype=float)
    x = x - x.mean(axis=0)

    u, s, vt = np.linalg.svd(x, full_matrices=False)

    scores = x @ vt[0]
    explained = (s[0] ** 2) / np.sum(s ** 2)

    return scores, explained, vt[0]


def corr(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)

    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0

    return float(np.corrcoef(a, b)[0, 1])


def simulate_panarchy():
    rng = np.random.default_rng(SEED)

    rows = []

    global_resource = 1.0
    global_hysteresis = 0.0

    module_strength = np.ones(MODULES) * 0.75
    module_adaptation = np.zeros(MODULES)

    for t in range(STEPS):
        disturbance = 0.0

        # repeated mild local stress creates antifragile local adaptation
        if 20 <= t <= 65 and t % 5 == 0:
            disturbance = 0.12
            module_adaptation += 0.025

        # global layer slowly degrades from coupling/resource exhaustion
        if t > 45:
            global_resource -= 0.006
            global_hysteresis += 0.008

        # late global shock
        if t > 85:
            global_resource -= 0.012
            global_hysteresis += 0.014

        global_resource = clamp01(global_resource)
        global_hysteresis = clamp01(global_hysteresis)

        for m in range(MODULES):
            noise = rng.normal(0, 0.015)

            local_recovery_strength = clamp01(
                module_strength[m]
                + module_adaptation[m]
                - disturbance
                + noise
            )

            local_persistence = clamp01(
                0.85
                + module_adaptation[m] * 0.4
                - disturbance * 0.25
                + noise
            )

            local_directional = clamp01(
                0.88
                + module_adaptation[m] * 0.25
                - disturbance * 0.20
                + noise
            )

            local_volatility = clamp01(
                0.15
                + disturbance
                + abs(noise)
            )

            local_gv = gv_scalar(GVEvidence(
                recovery_strength=local_recovery_strength,
                persistence=local_persistence,
                directional_degradation=local_directional,
                volatility_penalty=local_volatility,
            ))

            # global evidence decouples from local improvement
            global_recovery_strength = clamp01(global_resource)
            global_persistence = clamp01(1.0 - global_hysteresis)
            global_directional = clamp01(global_resource - global_hysteresis * 0.25)
            global_volatility = clamp01(0.20 + global_hysteresis)

            global_gv = gv_scalar(GVEvidence(
                recovery_strength=global_recovery_strength,
                persistence=global_persistence,
                directional_degradation=global_directional,
                volatility_penalty=global_volatility,
            ))

            rows.append({
                "time": t,
                "module": m,
                "local_recovery_strength": round(local_recovery_strength, 6),
                "local_persistence": round(local_persistence, 6),
                "local_directional": round(local_directional, 6),
                "local_volatility": round(local_volatility, 6),
                "local_gv": round(local_gv, 6),
                "global_resource": round(global_resource, 6),
                "global_hysteresis": round(global_hysteresis, 6),
                "global_gv": round(global_gv, 6),
                "coupling_gap": round(local_gv - global_gv, 6),
            })

    return rows


def analyze(rows):
    local_matrix = []
    global_matrix = []
    full_matrix = []

    local_gv = []
    global_gv = []

    # one row per module-time observation
    for r in rows:
        local_vec = [
            r["local_recovery_strength"],
            r["local_persistence"],
            r["local_directional"],
            1.0 - r["local_volatility"],
        ]

        global_vec = [
            r["global_resource"],
            1.0 - r["global_hysteresis"],
            r["global_gv"],
        ]

        full_vec = local_vec + global_vec + [
            1.0 - abs(r["coupling_gap"]),
        ]

        local_matrix.append(local_vec)
        global_matrix.append(global_vec)
        full_matrix.append(full_vec)

        local_gv.append(r["local_gv"])
        global_gv.append(r["global_gv"])

    local_pc1, local_explained, _ = pca_first_component(local_matrix)
    full_pc1, full_explained, _ = pca_first_component(full_matrix)

    if corr(local_gv, local_pc1) < 0:
        local_pc1 = -local_pc1

    combined_gv = [(l + g) / 2.0 for l, g in zip(local_gv, global_gv)]

    if corr(combined_gv, full_pc1) < 0:
        full_pc1 = -full_pc1

    local_alignment = corr(local_gv, local_pc1)
    full_alignment = corr(combined_gv, full_pc1)

    max_gap = max(abs(r["coupling_gap"]) for r in rows)

    late_rows = [r for r in rows if r["time"] >= 90]
    late_local_avg = float(np.mean([r["local_gv"] for r in late_rows]))
    late_global_avg = float(np.mean([r["global_gv"] for r in late_rows]))

    # hostile result rule
    if local_alignment >= 0.90 and full_explained < 0.75:
        result = "LOCAL_AXIS_SURVIVES_GLOBAL_AXIS_BREAKS"
    elif local_alignment >= 0.90 and full_alignment < 0.75:
        result = "LOCAL_ALIGNMENT_SURVIVES_GLOBAL_ALIGNMENT_BREAKS"
    elif full_alignment >= 0.85 and full_explained >= 0.75:
        result = "GV_SURVIVES_PANARCHY_TEST"
    else:
        result = "GV_PARTIAL_OR_INCONCLUSIVE"

    return {
        "result": result,
        "local_pc1_explained": round(float(local_explained), 6),
        "full_pc1_explained": round(float(full_explained), 6),
        "local_gv_pc1_correlation": round(float(local_alignment), 6),
        "combined_gv_full_pc1_correlation": round(float(full_alignment), 6),
        "max_local_global_gap": round(float(max_gap), 6),
        "late_local_gv_avg": round(late_local_avg, 6),
        "late_global_gv_avg": round(late_global_avg, 6),
    }


def main():
    rows = simulate_panarchy()
    metrics = analyze(rows)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    OUT_MD.write_text(f'''# GV Panarchy Adversarial Result

## Purpose

Attack the dominant recoverability axis hypothesis with local antifragility and global degradation.

## Result

`{metrics["result"]}`

## Metrics

| Metric | Value |
|---|---:|
| local PC1 explained variance | {metrics["local_pc1_explained"]} |
| full system PC1 explained variance | {metrics["full_pc1_explained"]} |
| local GV correlation with local PC1 | {metrics["local_gv_pc1_correlation"]} |
| combined GV correlation with full PC1 | {metrics["combined_gv_full_pc1_correlation"]} |
| max local-global GV gap | {metrics["max_local_global_gap"]} |
| late local GV average | {metrics["late_local_gv_avg"]} |
| late global GV average | {metrics["late_global_gv_avg"]} |

## Interpretation

This test intentionally lets local modules improve under mild stress while the global coupled system degrades.

If local GV remains high while global GV falls, the test exposes scale decoupling.

If full-system PC1 drops, recoverability is no longer cleanly scalar across scales.

## Scientific line

A local GV win is not enough.

A universal scalar must survive cross-scale coupling.
''', encoding="utf-8")

    print(metrics)
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
