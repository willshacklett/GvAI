import json
import numpy as np

from ci.godscore_ci import evaluate_series, save_result

N_STEPS = 140
N_NODES = 60


def make_series(seed: int = 42, scenario: str = "collapse"):
    rng = np.random.default_rng(seed)
    x = np.ones(N_NODES)
    series = []

    for t in range(N_STEPS):
        noise = rng.normal(0.0, 0.008, size=N_NODES)

        if scenario == "stable":
            if 35 <= t <= 45:
                noise += rng.normal(0.0, 0.010, size=N_NODES)
            drift = 0.0

        elif scenario == "recoverable":
            if 35 <= t <= 55:
                noise += rng.normal(0.0, 0.020, size=N_NODES)
            drift = 0.0
            if 56 <= t <= 80:
                x += -0.010 * (x - 1.0)

        elif scenario == "collapse":
            if t >= 35:
                noise += rng.normal(0.0, 0.018, size=N_NODES)
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


for scenario in ["stable", "recoverable", "collapse"]:
    payload = evaluate_series(make_series(scenario=scenario))
    out_path = f"ci/{scenario}_result.json"
    save_result(payload, out_path)

    print("=" * 60)
    print("SCENARIO:", scenario)
    print(json.dumps(payload, indent=2))
