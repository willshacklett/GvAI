import csv
import importlib.util
from pathlib import Path
import numpy as np

DYNAMIC_MODULE = Path("experiments/gv_falsification/dynamic_recovery_gv.py")

OUT_CSV = Path("reports/gv_regime_stability/regime_stability_results.csv")
OUT_MD = Path("reports/gv_regime_stability/regime_stability_summary.md")

SEEDS = range(1, 101)
COLLAPSE_AT = 800

ALPHAS = [0.75, 0.80, 0.85]

NOISE_LEVELS = [0.05, 0.10, 0.20, 0.35]
SLOWING_STRENGTHS = [0.0005, 0.0010, 0.0015, 0.0020]

# operational question:
# does the stable alpha region survive across regimes?


def load_dynamic_module():
    spec = importlib.util.spec_from_file_location(
        "dynamic_recovery_gv",
        DYNAMIC_MODULE
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def first_warning(gv, threshold):
    hits = np.where(gv < threshold)[0]
    return int(hits[0]) if len(hits) else None


def verdict(collapse_expected, warning):
    if collapse_expected:
        if warning is not None and warning < COLLAPSE_AT:
            return "EARLY_WARNING"
        return "MISS"

    if warning is not None:
        return "FALSE_POSITIVE"

    return "QUIET"


def critical_slowing_scenario(seed, noise_level, slowing_strength):
    rng = np.random.default_rng(seed)

    BASELINE = 10.0
    STEPS = 1200

    x = np.ones(STEPS) * BASELINE

    recovery_force = 0.45

    disturbance_times = list(range(100, STEPS, 20))

    for t in range(1, STEPS):

        if 350 < t < COLLAPSE_AT:
            recovery_force -= slowing_strength

        recovery_force = max(recovery_force, 0.001)

        noise = rng.normal(0, noise_level)

        x[t] = (
            x[t - 1]
            - recovery_force * (x[t - 1] - BASELINE)
            + noise
        )

        if t in disturbance_times:
            x[t] += 4.0

        if t >= COLLAPSE_AT:
            x[t] += (t - COLLAPSE_AT) * 0.15

    return x


def main():
    mod = load_dynamic_module()

    rows = []

    for alpha in ALPHAS:
        for noise_level in NOISE_LEVELS:
            for slowing_strength in SLOWING_STRENGTHS:

                for seed in SEEDS:

                    signal = critical_slowing_scenario(
                        seed,
                        noise_level,
                        slowing_strength
                    )

                    gv, trials, recovery_times, rho_values = mod.gv_equation(signal)

                    warning = first_warning(gv, alpha)

                    lead_time = (
                        COLLAPSE_AT - warning
                        if warning is not None else None
                    )

                    rows.append({
                        "alpha": alpha,
                        "noise_level": noise_level,
                        "slowing_strength": slowing_strength,
                        "seed": seed,
                        "warning": warning,
                        "lead_time": lead_time,
                        "verdict": verdict(True, warning),
                    })

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUT_CSV}")

    lines = [
        "# GV Regime Stability Map",
        "",
        "Purpose:",
        "",
        "Test whether the stable alpha region survives across:",
        "- noise regimes",
        "- slowing strengths",
        "",
        "| alpha | noise | slowing_strength | detection_rate | avg_lead_time |",
        "|---|---:|---:|---:|---:|",
    ]

    for alpha in ALPHAS:
        for noise_level in NOISE_LEVELS:
            for slowing_strength in SLOWING_STRENGTHS:

                subset = [
                    r for r in rows
                    if float(r["alpha"]) == alpha
                    and float(r["noise_level"]) == noise_level
                    and float(r["slowing_strength"]) == slowing_strength
                ]

                detections = sum(
                    1 for r in subset
                    if r["verdict"] == "EARLY_WARNING"
                )

                leads = [
                    int(r["lead_time"])
                    for r in subset
                    if r["lead_time"] not in {"", "None"}
                    and int(r["lead_time"]) > 0
                ]

                detection_rate = round(
                    detections / len(subset) * 100,
                    2
                )

                avg_lead = round(
                    float(np.mean(leads)),
                    2
                ) if leads else 0.0

                lines.append(
                    f"| {alpha} | "
                    f"{noise_level} | "
                    f"{slowing_strength} | "
                    f"{detection_rate}% | "
                    f"{avg_lead} |"
                )

    lines += [
        "",
        "## Interpretation",
        "",
        "This tests whether alpha-space remains stable under regime shifts.",
        "",
        "If the same alpha region survives across noise and slowing regimes,",
        "GV becomes more credible as a transferable recoverability detector.",
        "",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print()
    print(OUT_MD.read_text())


if __name__ == "__main__":
    main()
