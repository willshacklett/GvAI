import numpy as np
from gvai import run_sentinel_series, summarize_timeline


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


stable = run_sentinel_series(make_series(1, "stable"))
recoverable = run_sentinel_series(make_series(2, "recoverable"))
collapse = run_sentinel_series(make_series(3, "collapse"))

assert stable["fired"] is False
assert stable["status"] == "stable"

assert recoverable["fired"] is False
assert recoverable["status"] in ("stable", "warning")

assert collapse["fired"] is True
assert collapse["status"] == "collapse"
assert collapse["breach_step"] is not None
assert collapse["drift_step"] is not None
assert collapse["collapse_step"] is not None
assert collapse["lead_time"] is not None
assert collapse["lead_time"] > 0

summary = summarize_timeline(collapse)
assert summary["first_critical"] is not None
assert summary["first_collapse"] is not None

print("All API tests passed.")
