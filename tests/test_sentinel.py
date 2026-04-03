import numpy as np
from gvai import RecoverabilitySentinel

def run_scenario(seed: int, scenario: str):
    rng = np.random.default_rng(seed)
    x = np.ones(60)
    s = RecoverabilitySentinel()

    states = []
    final_state = None

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
        final_state = s.update(x)
        states.append(final_state)

    return s, final_state, states

# stable should remain stable
s, st, states = run_scenario(1, "stable")
assert s.fired is False
assert s.collapse_step is None
assert st.status == "stable"

# recoverable should not fire or collapse
s, st, states = run_scenario(2, "recoverable")
assert s.fired is False
assert s.collapse_step is None
assert st.status in ("stable", "warning")

# collapse should move through warning/critical/collapse
s, st, states = run_scenario(3, "collapse")
assert s.fired is True
assert s.breach_step is not None
assert s.drift_step is not None
assert s.collapse_step is not None
assert s.collapse_step > s.breach_step
assert st.lead_time is not None
assert st.lead_time > 0
assert st.status == "collapse"

statuses = [x.status for x in states]
assert "warning" in statuses or "critical" in statuses
assert "critical" in statuses
assert "collapse" in statuses

print("All sentinel state tests passed.")
