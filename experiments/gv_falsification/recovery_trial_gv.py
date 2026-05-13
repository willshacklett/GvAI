import numpy as np

SEED = 42
STEPS = 1200
BASELINE = 10.0
COLLAPSE_AT = 800
TRIAL_EVERY = 60
RECOVERY_WINDOW = 35
RETURN_TOLERANCE = 0.75


def inject_disturbance(x, t, size=4.0):
    if t < len(x):
        x[t] += size


def recovery_success(signal, t):
    start = t + 1
    end = min(t + RECOVERY_WINDOW, len(signal))

    if start >= end:
        return False

    future = signal[start:end]
    returned = np.any(np.abs(future - BASELINE) <= RETURN_TOLERANCE)
    return bool(returned)


def gv_from_recovery_trials(signal):
    trials = []
    gv = np.ones(len(signal))

    for t in range(100, len(signal), TRIAL_EVERY):
        success = recovery_success(signal, t)
        trials.append(success)

        recent = trials[-5:]
        recovery_rate = sum(recent) / len(recent)

        gv[t:] = recovery_rate

    return gv, trials


def first_warning(gv, threshold=0.65):
    hits = np.where(gv < threshold)[0]
    return int(hits[0]) if len(hits) else None


def scenario_true_collapse():
    rng = np.random.default_rng(SEED)
    x = np.ones(STEPS) * BASELINE

    for t in range(1, STEPS):
        noise = rng.normal(0, 0.15)
        if t > COLLAPSE_AT:
            x[t] = x[t-1] + 0.08 * (t - COLLAPSE_AT) + noise
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


SCENARIOS = {
    "true_collapse": scenario_true_collapse,
    "stable_noise": scenario_stable_noise,
    "noisy_but_recoverable": scenario_noisy_but_recoverable,
    "progressive_recovery_loss": scenario_progressive_recovery_loss,
}


def evaluate(name, maker):
    signal, collapse_expected = maker()
    gv, trials = gv_from_recovery_trials(signal)
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
        "trials_passed": int(sum(trials)),
        "trials_total": len(trials),
    }


def main():
    print("\nGV RECOVERY TRIAL HARNESS")
    print("Question: does GV drop only when recovery repeatedly fails?\n")

    failures = []

    for name, maker in SCENARIOS.items():
        result = evaluate(name, maker)
        print(result)
        if result["verdict"] != "PASS":
            failures.append(result)

    print("\nSUMMARY")
    if failures:
        print("GV STILL BROKE HERE:")
        for f in failures:
            print(f)
        raise SystemExit(1)

    print("GV survived recovery-trial falsification pass.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
