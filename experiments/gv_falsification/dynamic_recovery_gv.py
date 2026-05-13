import numpy as np

SEED = 42
STEPS = 1200
BASELINE = 10.0
COLLAPSE_AT = 800
TRIAL_EVERY = 20
RECOVERY_WINDOW = 45
RETURN_TOLERANCE = 0.75
DISTURBANCE_SIZE = 4.0


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def trial_times():
    return list(range(100, STEPS, TRIAL_EVERY))


def trend_slope(values):
    vals = [v for v in values if v is not None]

    if len(vals) < 3:
        return 0.0

    x = np.arange(len(vals))
    y = np.array(vals, dtype=float)

    return float(np.polyfit(x, y, 1)[0])


def recovery_time(signal, t):
    start = t + 1
    end = min(t + RECOVERY_WINDOW, len(signal))

    for i in range(start, end):
        if abs(signal[i] - BASELINE) <= RETURN_TOLERANCE:
            return i - t

    return None


def rho_total(signal, trial_index, trials, recovery_times):
    t = trials[trial_index]
    rt = recovery_times[trial_index]

    success = 1.0 if rt is not None else 0.0
    speed = 0.0 if rt is None else 1.0 - clamp01(rt / RECOVERY_WINDOW)

    recent = recovery_times[max(0, trial_index - 5):trial_index + 1]
    valid_recent = [v for v in recent if v is not None]

    slowing_penalty = clamp01(trend_slope(recent) / 8.0)

    # Relative recovery penalty:
    # GV should drop when recovery is still succeeding but taking much longer
    # than the system's own earlier recovery baseline.
    prior = recovery_times[:trial_index]
    valid_prior = [v for v in prior if v is not None]

    if rt is not None and len(valid_prior) >= 3:
        baseline_rt = max(1.0, float(np.median(valid_prior[:5])))
        relative_slowing_penalty = clamp01((rt - baseline_rt) / RECOVERY_WINDOW)
    elif rt is None:
        relative_slowing_penalty = 1.0
    else:
        relative_slowing_penalty = 0.0

    # Consecutive degradation penalty:
    # If recent recovery times keep getting worse, treat it as loss of recoverability density.
    if len(valid_recent) >= 3:
        recent_tail = valid_recent[-3:]
        consecutive_degradation = 1.0 if recent_tail[0] <= recent_tail[1] <= recent_tail[2] and recent_tail[-1] > recent_tail[0] else 0.0
    else:
        consecutive_degradation = 0.0

    drift_penalty = clamp01(abs(signal[t] - BASELINE) / 10.0)

    rho = (
        0.25 * success +
        0.20 * speed +
        0.20 * (1.0 - slowing_penalty) +
        0.20 * (1.0 - relative_slowing_penalty) +
        0.10 * (1.0 - consecutive_degradation) +
        0.05 * (1.0 - drift_penalty)
    )

    return clamp01(rho)


def gv_equation(signal, alpha=0.05):
    trials = trial_times()
    recovery_times = [recovery_time(signal, t) for t in trials]

    gv = np.ones(len(signal))
    rho_values = []

    for i, t in enumerate(trials):
        rho = rho_total(signal, i, trials, recovery_times)
        rho_values.append(rho)

        recent_rho = rho_values[-5:]
        gv_value = clamp01(float(np.mean(recent_rho)) + alpha)
        gv[t:] = gv_value

    return gv, trials, recovery_times, rho_values


def first_warning(gv, threshold=0.65):
    hits = np.where(gv < threshold)[0]
    return int(hits[0]) if len(hits) else None


def simulate_dynamic(recovery_force_fn, drift_fn, noise_sigma=0.10):
    rng = np.random.default_rng(SEED)
    x = np.ones(STEPS) * BASELINE
    trials = set(trial_times())

    for t in range(1, STEPS):
        force = recovery_force_fn(t)
        drift = drift_fn(t)
        noise = rng.normal(0, noise_sigma)

        disturbance = DISTURBANCE_SIZE if t in trials else 0.0

        pull_to_baseline = force * (BASELINE - x[t - 1])

        x[t] = x[t - 1] + pull_to_baseline + drift + disturbance + noise

    return x


def scenario_stable_dynamic():
    signal = simulate_dynamic(
        recovery_force_fn=lambda t: 0.45,
        drift_fn=lambda t: 0.0,
        noise_sigma=0.10,
    )
    return signal, False


def scenario_noisy_dynamic_recoverable():
    def noise_sigma_for_t(t):
        return 1.5 if 350 < t < 650 else 0.10

    rng = np.random.default_rng(SEED)
    x = np.ones(STEPS) * BASELINE
    trials = set(trial_times())

    for t in range(1, STEPS):
        force = 0.45
        noise = rng.normal(0, noise_sigma_for_t(t))
        disturbance = DISTURBANCE_SIZE if t in trials else 0.0
        pull_to_baseline = force * (BASELINE - x[t - 1])
        x[t] = x[t - 1] + pull_to_baseline + disturbance + noise

    return x, False


def scenario_critical_slowing_dynamic():
    def recovery_force(t):
        if t < 350:
            return 0.45

        if t < COLLAPSE_AT:
            weakening = (t - 350) / (COLLAPSE_AT - 350)
            return 0.45 * (1.0 - 0.85 * weakening)

        return 0.02

    def drift(t):
        if t < COLLAPSE_AT:
            return 0.0
        return 0.06 * ((t - COLLAPSE_AT) / 50.0)

    signal = simulate_dynamic(
        recovery_force_fn=recovery_force,
        drift_fn=drift,
        noise_sigma=0.10,
    )

    return signal, True


def scenario_abrupt_collapse_dynamic():
    def recovery_force(t):
        return 0.45 if t < COLLAPSE_AT else 0.02

    def drift(t):
        return 0.0 if t < COLLAPSE_AT else 0.08 * ((t - COLLAPSE_AT) / 30.0)

    signal = simulate_dynamic(
        recovery_force_fn=recovery_force,
        drift_fn=drift,
        noise_sigma=0.10,
    )

    return signal, True


SCENARIOS = {
    "stable_dynamic": scenario_stable_dynamic,
    "noisy_dynamic_recoverable": scenario_noisy_dynamic_recoverable,
    "critical_slowing_dynamic": scenario_critical_slowing_dynamic,
    "abrupt_collapse_dynamic": scenario_abrupt_collapse_dynamic,
}


def evaluate(name, maker):
    signal, collapse_expected = maker()
    gv, trials, recovery_times, rho_values = gv_equation(signal)

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
        "failed_recoveries": int(sum(1 for r in recovery_times if r is None)),
        "recovery_times": recovery_times,
    }


def main():
    print("\nGV DYNAMIC RECOVERY FALSIFICATION HARNESS")
    print("Disturbances occur inside the system update loop.")
    print("This tests actual recovery dynamics, not one-point spikes.\n")

    failures = []

    for name, maker in SCENARIOS.items():
        result = evaluate(name, maker)
        printable = dict(result)
        printable["recovery_times"] = result["recovery_times"][-8:]
        print(printable)

        if result["verdict"] != "PASS":
            failures.append(result)

    print("\nSUMMARY")
    if failures:
        print("GV STILL BROKE HERE:")
        for f in failures:
            print({
                "scenario": f["scenario"],
                "verdict": f["verdict"],
                "first_warning": f["first_warning"],
                "min_gv": f["min_gv"],
                "failed_recoveries": f["failed_recoveries"],
            })
        raise SystemExit(1)

    print("GV survived dynamic recovery falsification pass.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
