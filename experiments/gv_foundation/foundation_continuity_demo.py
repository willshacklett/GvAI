from gvai.foundational_gv import ContinuityState, gv_foundation

cases = [
    (
        "stable_recoverable",
        ContinuityState(
            recovery=0.96,
            persistence=0.95,
            directional_integrity=0.94,
            volatility=0.08,
        ),
    ),
    (
        "persistent_but_degrading",
        ContinuityState(
            recovery=0.55,
            persistence=0.88,
            directional_integrity=0.40,
            volatility=0.25,
        ),
    ),
    (
        "locally_stable_globally_fragile",
        ContinuityState(
            recovery=0.83,
            persistence=0.72,
            directional_integrity=0.46,
            volatility=0.32,
        ),
    ),
    (
        "irrecoverable",
        ContinuityState(
            recovery=0.12,
            persistence=0.18,
            directional_integrity=0.08,
            volatility=0.82,
        ),
    ),
]

print()
print("=== GV Foundational Continuity Demo ===")
print()

for name, state in cases:
    gv = gv_foundation(state)

    print({
        "case": name,
        "gv_foundation": gv,
        "state": state,
    })

print()
print("Interpretation:")
print("GV is treated as a continuity condition beneath persistence.")
print()
