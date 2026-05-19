from gvai.kernel.vitals import compute_vitals


def test_stable_vitals():
    result = compute_vitals(
        heartbeat={
            "gv": 0.95,
            "elasticity": 0.98,
            "debt": 0.2,
            "masking_distance": 0.02,
            "phase": "ELASTIC",
            "recoverability_state": "RECOVERABLE",
        },
        timeline={"time_in_current_phase": 2, "transition_count": 0},
        phase_lock={"phase_locked": False},
        recovery_pride={"recovery_pride": 0.9},
    )

    assert result["life_state"] == "ALIVE_STABLE"


def test_critical_vitals():
    result = compute_vitals(
        heartbeat={
            "gv": 0.5,
            "elasticity": 0.5,
            "debt": 4.0,
            "masking_distance": 0.2,
            "phase": "CASCADE_RISK",
            "recoverability_state": "CASCADE_RISK",
        },
        timeline={"time_in_current_phase": 4, "transition_count": 3},
        phase_lock={"phase_locked": True},
        recovery_pride={"recovery_pride": 0.1},
    )

    assert result["life_state"] == "CRITICAL"
