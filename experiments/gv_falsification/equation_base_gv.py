import numpy as np

SEED = 42
STEPS = 1200
BASELINE = 10.0
COLLAPSE_AT = 800
TRIAL_EVERY = 60
RECOVERY_WINDOW = 45
RETURN_TOLERANCE = 0.75

# GV equation base:
# Gv = ∫ ρ_total(x,t) + α
#
# Operational translation:
# ρ_total = recoverability density
# α = continuity anchor / baseline survivability offset
#
# Here, ρ_total is built from:
# - recovery success
# - recovery speed
# - recovery slowing trend
# - early-warning slope
# - drift away from baseline
#
# This is not final truth.
# This is the first executable version of the equation.


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def inject_disturbance(signal, t, size=4.0):
    if t < len(signal):
        signal[t] += size


def recovery_time(signal, t):
    start = t + 1
    end = min(t + RECOVERY_WINDOW, len(signal))

    for i in range(start, end):
        if abs(signal[i] - BASELINE) <= RETURN_TOLERANCE:
            return i - t

    return None


def trend_slope(values):
    vals = [v for v in values if v is not None]

    if len(vals) < 3:
        return 0.0

    x = np.arange(len(vals))
    y = np.array(vals, dtype=float)

    return float(np.polyfit(x, y, 1)[0])


def rho_total(signal, trial_index, trial_times, recovery_times):
    t = trial_times[trial_index]
    rt = recovery_times[trial_index]

    success = 1.0 if rt is not None else 0.0

    if rt is None:
        speed = 0.0
    else:
        speed = 1.0 - clamp01(rt / RECOVERY_WINDOW)

    recent = recovery_times[max(0, trial_index - 4):trial_index + 1]
    slowing = clamp01(trend_slope(recent) / RECOVERY_WINDOW)

    # Early-warning slope:
    # if recovery time is increasing, rho_total should fall BEFORE total failure.
    early_warning_penalty = clamp01(trend_slope(recent) / 12.0)

    drift = clamp01(abs(signal[t] - BASELINE) / 10.0)

    recoverability_density = (
        0.35 * success +
        0.25 * speed +
        0.15 * (1.0 - slowing) +
        0.15 * (1.0 - early_warning_penalty) +
        0.10 * (1.0 - drift)
    )

    return clamp01(recoverability_density)


def gv_equation(signal, alpha=0.05):
    trial_times = list(range(100, len(signal), TRIAL_EVERY))
    recovery_times = [recovery_time(signal, t) for t in trial_times]

    gv = np.ones(len(signal))
    rho_values = []

    for i, t in enumerate(trial_times):
        rho = rho_total(signal, i, trial_times, recovery_times)
        rho_values.append(rho)

        recent_rho = rho_values[-5:]

        # Executable equation:
        # Gv = ∫ρ_total(x,t) + α
        # The integral is approximated here as recent mean recoverability density.
        gv_value = clamp01(np.mean(recent_rho) + alpha)

        gv[t:] = gv_value

    return gv, trial_times, recovery_times, rho_values


def first_warning(gv, threshold=0.65):
    hits = np.where(gv < threshold)[0]
    return int(hits[0]) if len(hits) else None


def scenario_true_collapse():
    rng = np.random.default_rng(SEED)
    x = np.ones(STEPS) * BASELINE

    for t in range(1, STEPS):
        noise = rng.normal(0, 0.15)
        if t > COLLAPSE_AT:
            x[t] = x[t - 1] + 0.08 * (t - COLLAPSE_AT) + noise
        else:
            x[t] = BASELINE + noise

    for t in range(100, STEPS, TRIAL_EVERY):
        inject_disturbance(x, t)

    return x, True


def scenario_stable_noise():
    rng = np.random.default_rng(SEED)
    x = BASELINE + rng.normal(0, 0.25, STEPS)

    for t in range(100, STEPS, TRIAL_EVERY):
        inject_disturbance(x, t)

    return x, False


def scenario_noisy_but_recoverable():
    rng = np.random.default_rng(SEED)
    x = np.ones(STEPS) * BASELINE

    for t in range(STEPS):
        noise = rng.normal(0, 0.2)
        if 350 < t < 650:
            noise += rng.normal(0, 3.0)
        x[t] = BASELINE + noise

    for t in range(100, STEPS, TRIAL_EVERY):
        inject_disturbance(x, t)

    return x, False


def scenario_progressive_recovery_loss():
    rng = np.random.default_rng(SEED)
    x = np.ones(STEPS) * BASELINE

    for t in range(1, STEPS):
        noise = rng.normal(0, 0.15)

        if t < COLLAPSE_AT:
            x[t] = BASELINE + noise
        else:
            drift = 0.025 * (t - COLLAPSE_AT)
            x[t] = BASELINE + drift + noise

    for t in range(100, STEPS, TRIAL_EVERY):
        inject_disturbance(x, t)

    return x, True


def scenario_critical_slowing_before_collapse():
    """
    Core GV scientific test.

    The visible signal stays near baseline before COLLAPSE_AT,
    but the system's recovery force weakens earlier.

    This creates critical slowing down:
    - same disturbance size
    - progressively weaker pull back to baseline
    - recovery takes longer before collapse is obvious

    If GV is real as recoverability loss, it should warn before COLLAPSE_AT here.
    """
    rng = np.random.default_rng(SEED)
    x = np.ones(STEPS) * BASELINE

    recovery_force = 0.45

    for t in range(1, STEPS):
        noise = rng.normal(0, 0.10)

        if 350 < t < COLLAPSE_AT:
            # recovery force gradually weakens before visible collapse
            weakening = (t - 350) / (COLLAPSE_AT - 350)
            recovery_force = 0.45 * (1.0 - 0.85 * weakening)

        if t >= COLLAPSE_AT:
            # after collapse, drift overwhelms recovery
            recovery_force = 0.02
            external_drift = 0.06 * (t - COLLAPSE_AT)
        else:
            external_drift = 0.0

        pull_to_baseline = recovery_force * (BASELINE - x[t - 1])
        x[t] = x[t - 1] + pull_to_baseline + external_drift + noise

    for t in range(100, STEPS, TRIAL_EVERY):
        inject_disturbance(x, t)

    return x, True


SCENARIOS = {
    "true_collapse": scenario_true_collapse,
    "stable_noise": scenario_stable_noise,
    "noisy_but_recoverable": scenario_noisy_but_recoverable,
    "progressive_recovery_loss": scenario_progressive_recovery_loss,
    "critical_slowing_before_collapse": scenario_critical_slowing_before_collapse,
}


def evaluate(name, maker):
    signal, collapse_expected = maker()
    gv, trial_times, recovery_times, rho_values = gv_equation(signal)

    warning = first_warning(gv)
    warned_before_collapse = warning is not None and warning < COLLAPSE_AT

    if collapse_expected and warned_before_collapse:
        verdict = "PASS"
    elif collapse_expected:
        verdict = "FAIL_MISSED_COLLAPSE"
    elif warning is not None:
        verdict = "FAIL_FALSE_POSITIVE"
    else:
        verdict = "PASS"

    return {
        "scenario": name,
        "collapse_expected": collapse_expected,
        "first_warning": warning,
        "verdict": verdict,
        "min_gv": round(float(np.nanmin(gv)), 4),
        "mean_rho": round(float(np.mean(rho_values)), 4),
        "failed_recoveries": sum(1 for r in recovery_times if r is None),
        "trial_count": len(trial_times),
    }


def main():
    print("\nGV EQUATION-BASE FALSIFICATION HARNESS")
    print("Base equation: Gv = integral(rho_total(x,t)) + alpha")
    print("rho_total = operational recoverability density\n")

    failures = []

    for name, maker in SCENARIOS.items():
        result = evaluate(name, maker)
        print(result)
        if result["verdict"] != "PASS":
            failures.append(result)

    print("\nSUMMARY")
    if failures:
        print("GV EQUATION BASE STILL BROKE HERE:")
        for f in failures:
            print(f)
        raise SystemExit(1)

    print("GV equation-base harness survived this pass.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
