import numpy as np
from gvai import RecoverabilitySentinel

N_STEPS = 140
N_NODES = 60

rng = np.random.default_rng(42)
x = np.ones(N_NODES)

sentinel = RecoverabilitySentinel()

print("t | mean | var | fired | status   | lead_time")
print("-" * 54)

for t in range(N_STEPS):
    noise = rng.normal(0.0, 0.008, size=N_NODES)

    if t >= 35:
        noise += rng.normal(0.0, 0.018, size=N_NODES)

    drift = 0.0
    if t >= 60:
        drift = 0.006
    if t >= 80:
        drift = 0.012

    x = x + noise + drift

    state = sentinel.update(x)
    info = sentinel.explain(state)

    if t % 5 == 0 or state.breach_now or state.drift_now or state.collapse_now:
        print(
            f"{t:3d} | "
            f"{state.mean:5.3f} | "
            f"{state.var:7.4f} | "
            f"{str(state.fired):5s} | "
            f"{state.status:8s} | "
            f"{str(state.lead_time)}"
        )

print("\nFinal:")
print(info)
