import csv
from pathlib import Path
import numpy as np

from gvai.universal_scalar import GVEvidence, gv_scalar

OUT_CSV = Path("reports/gv_dominant_axis/dominant_axis_cases.csv")
OUT_MD = Path("reports/gv_dominant_axis/DOMINANT_AXIS_RESULT.md")

# Synthetic cross-domain evidence matrix.
# Rows intentionally include multiple domains and multiple recoverability dimensions.
CASES = [
    {
        "case": "software_stable",
        "domain": "software",
        "recovery_strength": 1.00,
        "persistence": 1.00,
        "directional_degradation": 1.00,
        "volatility_penalty": 0.05,
        "recovery_time": 0.05,
        "hysteresis": 0.02,
        "future_sensitivity": 0.05,
    },
    {
        "case": "queue_transient_surge",
        "domain": "queue",
        "recovery_strength": 0.82,
        "persistence": 0.88,
        "directional_degradation": 0.82,
        "volatility_penalty": 0.55,
        "recovery_time": 0.25,
        "hysteresis": 0.15,
        "future_sensitivity": 0.22,
    },
    {
        "case": "service_persistent_degradation",
        "domain": "service",
        "recovery_strength": 0.42,
        "persistence": 0.34,
        "directional_degradation": 0.28,
        "volatility_penalty": 0.45,
        "recovery_time": 0.70,
        "hysteresis": 0.62,
        "future_sensitivity": 0.66,
    },
    {
        "case": "biology_slow_recovery",
        "domain": "biology",
        "recovery_strength": 0.38,
        "persistence": 0.42,
        "directional_degradation": 0.48,
        "volatility_penalty": 0.30,
        "recovery_time": 0.62,
        "hysteresis": 0.44,
        "future_sensitivity": 0.58,
    },
    {
        "case": "economics_recovery_loss",
        "domain": "economics",
        "recovery_strength": 0.30,
        "persistence": 0.24,
        "directional_degradation": 0.34,
        "volatility_penalty": 0.42,
        "recovery_time": 0.78,
        "hysteresis": 0.70,
        "future_sensitivity": 0.80,
    },
    {
        "case": "generic_irrecoverable_failure",
        "domain": "generic",
        "recovery_strength": 0.05,
        "persistence": 0.05,
        "directional_degradation": 0.05,
        "volatility_penalty": 0.90,
        "recovery_time": 0.98,
        "hysteresis": 0.96,
        "future_sensitivity": 0.95,
    },
    {
        "case": "antifragile_training_response",
        "domain": "biology",
        "recovery_strength": 0.92,
        "persistence": 0.95,
        "directional_degradation": 0.96,
        "volatility_penalty": 0.25,
        "recovery_time": 0.18,
        "hysteresis": 0.05,
        "future_sensitivity": 0.10,
    },
]


def pca_first_component(matrix):
    x = np.array(matrix, dtype=float)
    x = x - x.mean(axis=0)
    u, s, vt = np.linalg.svd(x, full_matrices=False)

    component = vt[0]
    scores = x @ component
    explained = (s[0] ** 2) / np.sum(s ** 2)

    return scores, explained, component


def corr(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)

    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0

    return float(np.corrcoef(a, b)[0, 1])


def main():
    rows = []

    # Damage-style metrics are inverted where needed so higher = more recoverable.
    matrix = []

    for case in CASES:
        evidence = GVEvidence(
            recovery_strength=case["recovery_strength"],
            persistence=case["persistence"],
            directional_degradation=case["directional_degradation"],
            volatility_penalty=case["volatility_penalty"],
        )

        gv = gv_scalar(evidence)

        # Independent recoverability matrix.
        # Higher should mean better recoverability.
        recoverability_vector = [
            case["recovery_strength"],
            case["persistence"],
            case["directional_degradation"],
            1.0 - case["volatility_penalty"],
            1.0 - case["recovery_time"],
            1.0 - case["hysteresis"],
            1.0 - case["future_sensitivity"],
        ]

        matrix.append(recoverability_vector)

        rows.append({
            "case": case["case"],
            "domain": case["domain"],
            "gv": gv,
            "recovery_strength": case["recovery_strength"],
            "persistence": case["persistence"],
            "directional_degradation": case["directional_degradation"],
            "volatility_penalty": case["volatility_penalty"],
            "recovery_time": case["recovery_time"],
            "hysteresis": case["hysteresis"],
            "future_sensitivity": case["future_sensitivity"],
        })

    pc1_scores, explained, component = pca_first_component(matrix)

    # Flip sign if needed so high PC1 aligns with high GV.
    if corr([r["gv"] for r in rows], pc1_scores) < 0:
        pc1_scores = -pc1_scores
        component = -component

    gv_values = [r["gv"] for r in rows]
    alignment = corr(gv_values, pc1_scores)

    for row, score in zip(rows, pc1_scores):
        row["pc1_recoverability_score"] = round(float(score), 6)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    if explained >= 0.70 and alignment >= 0.85:
        result = "GV_ALIGNS_WITH_DOMINANT_AXIS"
    elif alignment >= 0.70:
        result = "GV_PARTIALLY_ALIGNS_WITH_DOMINANT_AXIS"
    else:
        result = "GV_FAILS_DOMINANT_AXIS_TEST"

    OUT_MD.write_text(f'''# GV Dominant Recoverability Axis Result

## Purpose

Test whether GV behaves like a dominant recoverability axis rather than claiming to explain every dimension.

## Result

`{result}`

## Metrics

| Metric | Value |
|---|---:|
| PC1 explained variance | {round(float(explained), 4)} |
| GV correlation with PC1 | {round(float(alignment), 4)} |

## Interpretation

If PC1 explained variance is high, recoverability in this test set is mostly scalar-like.

If GV aligns strongly with PC1, GV is behaving like a dominant recoverability axis.

If PC1 explained variance is low, recoverability is fundamentally multi-axis in this set.

If GV correlation with PC1 is low, GV is not capturing the dominant axis.

## Scientific line

This does not prove GV is universal.

It tests whether GV is aligned with the leading recoverability structure across cross-domain evidence.

## Output

See:

`reports/gv_dominant_axis/dominant_axis_cases.csv`
''', encoding="utf-8")

    print({
        "result": result,
        "pc1_explained_variance": round(float(explained), 4),
        "gv_pc1_correlation": round(float(alignment), 4),
        "out_csv": str(OUT_CSV),
    })


if __name__ == "__main__":
    main()
