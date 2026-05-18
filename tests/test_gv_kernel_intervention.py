from gvai.kernel.intervention import decide_intervention


def test_stable_state_continues():
    result = decide_intervention({
        "trajectory_mode": "STABLE",
        "rolling_gv": 0.88,
        "drift_trend": 0.0,
        "recoverability_trend": 0.0,
    })

    assert result["decision"] == "continue"
    assert result["intervention_level"] == "NONE"


def test_degrading_state_intervenes():
    result = decide_intervention({
        "trajectory_mode": "DEGRADING",
        "rolling_gv": 0.42,
        "drift_trend": 0.18,
        "recoverability_trend": 0.2,
    })

    assert result["decision"] == "intervene"
    assert result["intervention_level"] == "HARD"
    assert any("rollback" in action.lower() for action in result["actions"])
