from gvai.change_impact import evaluate_change_impact


def test_low_risk_change_allows():
    result = evaluate_change_impact({
        "new_tasks": 1,
        "manager_capacity": 5,
        "training_readiness": 0.95,
        "clarity": 0.95,
        "recovery_plan_strength": 0.9,
        "active_changes": 1,
        "safe_change_limit": 5,
    })
    assert result["mode"] == "ALLOW"
    assert result["gv"] >= 0.75


def test_overloaded_change_blocks():
    result = evaluate_change_impact({
        "new_tasks": 10,
        "manager_capacity": 2,
        "training_readiness": 0.2,
        "clarity": 0.2,
        "recovery_plan_strength": 0.1,
        "active_changes": 6,
        "safe_change_limit": 2,
    })
    assert result["mode"] == "BLOCK"
    assert result["gv"] < 0.45


def test_mid_risk_change_qualifies():
    result = evaluate_change_impact({
        "new_tasks": 3,
        "manager_capacity": 5,
        "training_readiness": 0.6,
        "clarity": 0.65,
        "recovery_plan_strength": 0.5,
        "active_changes": 2,
        "safe_change_limit": 4,
    })
    assert result["mode"] == "QUALIFY"
