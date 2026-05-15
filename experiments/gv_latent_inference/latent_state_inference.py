import csv
from pathlib import Path
import numpy as np

from gvai.universal_scalar import GVEvidence, gv_scalar

OUT_CSV = Path("reports/gv_latent_inference/latent_state_cases.csv")
OUT_MD = Path("reports/gv_latent_inference/LATENT_STATE_RESULT.md")

SEED = 42
STEPS = 260


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
    delayed_masking = 1.0

    rows = []

    for t in range(STEPS):
        disturbance = 0.0

        # periodic operational disturbances
        if t % 28 == 0 and t > 0:
            disturbance = 0.32

        # hidden degradation begins
        if t > 85:
            hidden_damage += 0.0035

        # acceleration region
        if t > 165:
            hidden_damage += 0.008

        hidden_damage = clamp01(hidden_damage)

        true_recovery = clamp01(1.0 - hidden_damage)

        # masking layer temporarily hides degradation
        if hidden_damage < 0.45:
            delayed_masking = 1.0
        else:
            delayed_masking = clamp01(1.0 - (hidden_damage - 0.45) * 1.8)

        effective_recovery = true_recovery * delayed_masking

        observable_state += disturbance

        observable_state -= effective_recovery * observable_state * 0.19

        observable_state += rng.normal(0, 0.018)

        observable_error = abs(observable_state)

        recent = rows[-24:]

        if len(recent) < 12:
            recovery_strength = 1.0
            persistence = 1.0
            directional = 1.0
            volatility_penalty = 0.0
            hysteresis = 0.0
        else:
            recent_errors = np.array([r["observable_error"] for r in recent])

            slope = float(np.mean(np.diff(recent_errors)))
            variance = float(np.var(recent_errors))

            shock_peaks = sorted(recent_errors)[-3:]
            recovery_floor = sorted(recent_errors)[:3]

            hysteresis = float(np.mean(shock_peaks) - np.mean(recovery_floor))

            recovery_strength = clamp01(1.0 - np.mean(recent_errors) * 3.5)
            persistence = clamp01(1.0 - max(0.0, slope) * 15.0)
            directional = clamp01(1.0 - max(0.0, slope) * 22.0)
            volatility_penalty = clamp01(
                variance * 25.0 + hysteresis * 3.0
            )

        gv = gv_scalar(GVEvidence(
            recovery_strength=recovery_strength,
            persistence=persistence,
            directional_degradation=directional,
            volatility_penalty=volatility_penalty,
        ))

        # latent inference estimate from observables only
        inferred_hidden_deg = clamp01(
            (1.0 - gv) * 0.55
            + hysteresis * 0.35
            + volatility_penalty * 0.25
        )

        # naive baseline estimator
        naive_estimator = clamp01(observable_error * 1.7)

        rows.append({
            "time": t,
            "hidden_damage": round(hidden_damage, 6),
            "true_recovery": round(true_recovery, 6),
            "delayed_masking": round(delayed_masking, 6),
            "observable_state": round(float(observable_state), 6),
            "observable_error": round(float(observable_error), 6),
            "recovery_strength": round(recovery_strength, 6),
            "persistence": round(persistence, 6),
            "directional": round(directional, 6),
            "volatility_penalty": round(volatility_penalty, 6),
            "hysteresis": round(hysteresis, 6),
            "gv": round(gv, 6),
            "inferred_hidden_deg": round(inferred_hidden_deg, 6),
            "naive_estimator": round(naive_estimator, 6),
        })

    return rows


def main():
    rows = simulate()

    hidden = [r["hidden_damage"] for r in rows]
    inferred = [r["inferred_hidden_deg"] for r in rows]
    naive = [r["naive_estimator"] for r in rows]
    gv = [r["gv"] for r in rows]

    gv_corr = corr(hidden, [1.0 - x for x in gv])
    inference_corr = corr(hidden, inferred)
    naive_corr = corr(hidden, naive)

    # lead detection
    lead_idx = None

    for r in rows:
        if (
            r["inferred_hidden_deg"] >= 0.50
            and r["hidden_damage"] < 0.75
        ):
            lead_idx = r["time"]
            break

    collapse_idx = None

    for r in rows:
        if r["hidden_damage"] >= 0.75:
            collapse_idx = r["time"]
            break

    lead_time = None

    if lead_idx is not None and collapse_idx is not None:
        lead_time = collapse_idx - lead_idx

    if (
        inference_corr > naive_corr + 0.10
        and inference_corr >= 0.75
    ):
        result = "GV_LATENT_INFERENCE_SURVIVES"

    elif inference_corr > naive_corr:
        result = "GV_LATENT_INFERENCE_PARTIAL"

    else:
        result = "GV_LATENT_INFERENCE_FAILS"

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    OUT_MD.write_text(f'''# GV Latent State Inference Result

## Purpose

Test whether hidden degradation can be inferred from observable continuity behavior.

## Result

`{result}`

## Metrics

| Metric | Value |
|---|---:|
| GV inverse correlation with hidden damage | {round(gv_corr, 6)} |
| latent inference correlation | {round(inference_corr, 6)} |
| naive baseline correlation | {round(naive_corr, 6)} |
| inference lead index | {lead_idx} |
| collapse index | {collapse_idx} |
| lead time | {lead_time} |

## Interpretation

The hidden layer is intentionally partially masked.

The observable layer does not directly expose hidden degradation.

The question is whether continuity behavior still contains enough information
to infer latent recoverability loss.

## Scientific posture

This test is adversarial.

The hidden layer attempts to remain concealed while degrading internally.

GV survives only if observable continuity still leaks recoverability information.
''', encoding="utf-8")

    print({
        "result": result,
        "gv_corr": round(gv_corr, 6),
        "inference_corr": round(inference_corr, 6),
        "naive_corr": round(naive_corr, 6),
        "lead_time": lead_time,
    })

    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
