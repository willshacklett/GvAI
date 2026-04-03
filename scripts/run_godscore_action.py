import json
import os
import sys
import numpy as np

from ci.godscore_ci import evaluate_series

N_STEPS = 140
N_NODES = 60


def env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name, str(default)).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def env_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


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
            raise ValueError(f"bad scenario: {scenario}")

        x = x + noise + drift
        series.append(x.copy())

    return series


def write_github_output(key: str, value) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"{key}={value}\n")


def main() -> int:
    scenario = env_str("GODSCORE_SCENARIO", "collapse")
    enforce = env_flag("GODSCORE_ENFORCE", False)
    fail_on_warning = env_flag("GODSCORE_FAIL_ON_WARNING", False)

    payload = evaluate_series(
        make_series(scenario=scenario),
        fail_on_critical=enforce,
        fail_on_warning=fail_on_warning,
    )

    os.makedirs("ci", exist_ok=True)
    with open("ci/action_result.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("=== GodScore CI Result ===")
    print(json.dumps(payload, indent=2))
    print()
    print(f"godscore={payload['godscore']}")
    print(f"status={payload['status']}")
    print(f"passed={str(payload['passed']).lower()}")

    write_github_output("godscore", payload["godscore"])
    write_github_output("status", payload["status"])
    write_github_output("passed", str(payload["passed"]).lower())

    if not payload["passed"]:
        print("\nBuild marked as failed by GodScore CI.")
        return 1

    print("\nBuild passed GodScore CI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
