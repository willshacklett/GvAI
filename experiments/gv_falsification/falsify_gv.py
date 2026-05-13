import numpy as np

SEED = 42
STEPS = 1200
WINDOW = 80
COLLAPSE_AT = 800


def rolling_std(x, window):
    out = np.full(len(x), np.nan)
    for i in range(window, len(x)):
        out[i] = np.std(x[i-window:i])
    return out


def rolling_recovery_lag(x, baseline, window):
    out = np.full(len(x), np.nan)
    threshold = baseline * 1.10
    for i in range(window, len(x)):
        recent = x[i-window:i]
        out[i] = np.mean(recent > threshold)
    return out


def normalize(x):
    x = np.nan_to_num(x, nan=0.0)
    mx = np.max(x)
    return x / mx if mx > 0 else x


def gv_score(signal):
    baseline = np.median(signal[:200])
    volatility = normalize(rolling_std(signal, WINDOW))
    lag = normalize(rolling_recovery_lag(signal, baseline, WINDOW))
    risk = 0.55 * lag + 0.45 * volatility
    return 1.0 - risk


def first_warning(gv, threshold=0.65):
    hits = np.where(gv < threshold)[0]
    return int(hits[0]) if len(hits) else None


def scenario_true_collapse():
    rng = np.random.default_rng(SEED)
    x = np.ones(STEPS) * 10.0
    for t in range(1, STEPS):
        noise = rng.normal(0, 0.15)
        if t > COLLAPSE_AT:
            x[t] = x[t-1] + 0.04 * (t - COLLAPSE_AT) + noise
        else:
            x[t] = 10.0 + noise
    return x, True


def scenario_stable_noise():
    rng = np.random.default_rng(SEED)
    x = 10.0 + rng.normal(0, 0.25, STEPS)
    return x, False


def scenario_noisy_but_recoverable():
    rng = np.random.default_rng(SEED)
    x = np.ones(STEPS) * 10.0
    for t in range(STEPS):
        noise = rng.normal(0, 0.2)
        if 350 < t < 650:
            noise += rng.normal(0, 3.0)
        x[t] = 10.0 + noise
    return x, False


def scenario_hidden_failure():
    rng = np.random.default_rng(SEED)
    x = 10.0 + rng.normal(0, 0.15, STEPS)
    return x, True


SCENARIOS = {
    "true_collapse": scenario_true_collapse,
    "stable_noise": scenario_stable_noise,
    "noisy_but_recoverable": scenario_noisy_but_recoverable,
    "hidden_failure": scenario_hidden_failure,
}


def evaluate(name, maker):
    signal, collapse_expected = maker()
    gv = gv_score(signal)
    warning = first_warning(gv)

    warned_before_collapse = (
        warning is not None and warning < COLLAPSE_AT
    )

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
    }


def main():
    print("\nGV FALSIFICATION HARNESS")
    print("Question: does GV detect loss of recoverability, or merely react to noise?\n")

    failures = []

    for name, maker in SCENARIOS.items():
        result = evaluate(name, maker)
        print(result)
        if result["verdict"] != "PASS":
            failures.append(result)

    print("\nSUMMARY")
    if failures:
        print("GV BROKE HERE:")
        for f in failures:
            print(f)
        raise SystemExit(1)

    print("GV survived this first falsification pass.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
