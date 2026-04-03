import numpy as np
from ci.godscore_ci import evaluate_series


def make_series(seed: int, scenario: str):
    rng = np.random.default_rng(seed)
    x = np.ones(60)
    series = []

    for t in range(140):
        noise = rng.normal(0.0, 0.008, size=60)

        if scenario == "stable":
            if 35 <= t <= 45:
                noise += rng.normal(0.0, 0.010, size=60)
            drift = 0.0

        elif scenario == "recoverable":
            if 35 <= t <= 55:
                noise += rng.normal(0.0, 0.020, size=60)
            drift = 0.0
            if 56 <= t <= 80:
                x += -0.010 * (x - 1.0)

        elif scenario == "collapse":
            if t >= 35:
                noise += rng.normal(0.0, 0.018, size=60)
            drift = 0.0
            if t >= 60:
                drift = 0.006
            if t >= 80:
                drift = 0.012
        else:
            raise ValueError("bad scenario")

        x = x + noise + drift
        series.append(x.copy())

    return series


stable = evaluate_series(make_series(1, "stable"))
recoverable = evaluate_series(make_series(2, "recoverable"))
collapse = evaluate_series(make_series(3, "collapse"))

assert stable["status"] == "stable"
assert stable["passed"] is True
assert stable["godscore"] >= 90

assert recoverable["status"] in ("stable", "warning")
assert recoverable["passed"] is True
assert recoverable["godscore"] >= 70

assert collapse["status"] == "collapse"
assert collapse["passed"] is False
assert collapse["lead_time"] is not None
assert collapse["godscore"] <= 10

print("All GodScore CI tests passed.")
