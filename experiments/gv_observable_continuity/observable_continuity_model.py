import csv
from pathlib import Path
import numpy as np

from gvai.universal_scalar import GVEvidence, gv_scalar

OUT_CSV = Path("reports/gv_observable_continuity/observable_continuity_cases.csv")
OUT_MD = Path("reports/gv_observable_continuity/OBSERVABLE_CONTINUITY_RESULT.md")

SEED = 42
STEPS = 180


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def corr(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)

    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0

    return float(np.corrcoef(a, b)[0, 1])


def simulate():
    rng = np.random.default_rng(SEED)

    hidden_recoverability = 1.0
    hidden_damage = 0.0
    observable_state = 0.0

    rows = []

    for t in range(STEPS):
        disturbance = 0.0

        if t % 25 == 0 and t > 0:
            disturbance = 0.35

        # hidden layer slowly weakens after step 80
        if t > 80:
            hidden_damage += 0.006

        # hidden damage reduces true recovery force
        true_recovery_force = clamp01(1.0 - hidden_damage)

        # observable system gets disturbed, then hidden recovery pulls it back
        observable_state += disturbance
        observable_state -= true_recovery_force * observable_state * 0.22
        observable_state += rng.normal(0, 0.015)

        observable_error = abs(observable_state)

        # estimate observable recovery features from recent history
        recent_rows = rows[-20:]

        if len(recent_rows) < 8:
            recovery_strength = 1.0
            persistence = 1.0
            directional_degradation = 1.0
            volatility_penalty = 0.0
        else:
            recent_errors = np.array([r["observable_error"] for r in recent_rows])
            recent_slope = float(np.mean(np.diff(recent_errors)))
            volatility = float(np.std(recent_errors))

            recovery_strength = clamp01(1.0 - np.mean(recent_errors) * 3.0)
            persistence = clamp01(1.0 - max(0.0, recent_slope) * 12.0)
            directional_degradation = clamp01(1.0 - max(0.0, recent_slope) * 18.0)
            volatility_penalty = clamp01(volatility * 8.0)

        gv_observed = gv_scalar(GVEvidence(
            recovery_strength=recovery_strength,
            persistence=persistence,
            directional_degradation=directional_degradation,
            volatility_penalty=volatility_penalty,
        ))

        rows.append({
            "time": t,
            "hidden_recoverability": round(true_recovery_force, 6),
            "hidden_damage": round(clamp01(hidden_damage), 6),
            "observable_state": round(float(observable_state), 6),
            "observable_error": round(float(observable_error), 6),
            "recovery_strength_est": round(recovery_strength, 6),
            "persistence_est": round(persistence, 6),
            "directional_degradation_est": round(directional_degradation, 6),
            "volatility_penalty_est": round(volatility_penalty, 6),
            "gv_observed": round(gv_observed, 6),
        })

    return rows


def main():
    rows = simulate()

    hidden = [r["hidden_recoverability"] for r in rows]
    gv = [r["gv_observed"] for r in rows]

    early = [r for r in rows if r["time"] < 80]
    late = [r for r in rows if r["time"] >= 130]

    metrics = {
        "gv_hidden_corr": round(corr(gv, hidden), 6),
        "early_gv_avg": round(float(np.mean([r["gv_observed"] for r in early])), 6),
        "late_gv_avg": round(float(np.mean([r["gv_observed"] for r in late])), 6),
        "early_hidden_avg": round(float(np.mean([r["hidden_recoverability"] for r in early])), 6),
        "late_hidden_avg": round(float(np.mean([r["hidden_recoverability"] for r in late])), 6),
    }

    if metrics["gv_hidden_corr"] >= 0.80 and metrics["late_gv_avg"] < metrics["early_gv_avg"]:
        result = "OBSERVABLE_GV_TRACKS_HIDDEN_RECOVERABILITY"
    elif metrics["late_gv_avg"] < metrics["early_gv_avg"]:
        result = "OBSERVABLE_GV_PARTIALLY_TRACKS_HIDDEN_RECOVERABILITY"
    else:
        result = "OBSERVABLE_GV_FAILS_HIDDEN_RECOVERABILITY_TEST"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    OUT_MD.write_text(f'''# GV Observable Continuity Result

## Purpose

Test whether observable behavior can infer hidden recoverability loss.

## Result

`{result}`

## Metrics

| Metric | Value |
|---|---:|
| GV correlation with hidden recoverability | {metrics["gv_hidden_corr"]} |
| early GV average | {metrics["early_gv_avg"]} |
| late GV average | {metrics["late_gv_avg"]} |
| early hidden recoverability average | {metrics["early_hidden_avg"]} |
| late hidden recoverability average | {metrics["late_hidden_avg"]} |

## Interpretation

The hidden layer is not directly measured by GV.

GV only sees observable recovery behavior.

If GV tracks hidden recoverability anyway, that supports the idea:

observable continuity constrains invisible structure.

## Scientific line

GV is not direct observation of the hidden layer.

GV is inference from observable continuity.
''', encoding="utf-8")

    print({"result": result, **metrics})
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
