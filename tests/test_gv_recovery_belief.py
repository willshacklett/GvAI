from gvai.kernel.recovery_belief import compute_recovery_belief


def test_strong_belief():
    result = compute_recovery_belief({
        "life_state": "ALIVE_STABLE",
        "pulse": 0.95,
        "breath": 0.96,
        "strain": 0.05,
        "hidden_stress": 0.02,
        "recovery_pride": 0.9,
        "phase_locked": False,
    })

    assert result["belief_mode"] == "BELIEVES_AND_RECOVERS"


def test_low_belief_or_collapse():
    result = compute_recovery_belief({
        "life_state": "CRITICAL",
        "pulse": 0.3,
        "breath": 0.3,
        "strain": 0.9,
        "hidden_stress": 0.2,
        "recovery_pride": 0.05,
        "phase_locked": True,
    })

    assert result["belief_mode"] in {
        "LOW_BELIEF_RECOVERY",
        "BELIEF_COLLAPSE_RISK",
    }
