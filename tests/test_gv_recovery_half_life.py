from gvai.kernel.recovery_half_life import estimate_recovery_half_life


def test_insufficient_data():
    result = estimate_recovery_half_life({"events": []})
    assert result["status"] == "INSUFFICIENT_DATA"


def test_recovered_half_debt():
    result = estimate_recovery_half_life({
        "events": [
            {"debt": 0.2},
            {"debt": 2.0},
            {"debt": 1.4},
            {"debt": 0.9},
        ]
    })

    assert result["status"] == "RECOVERED_HALF_DEBT"
    assert result["half_life_events"] == 2


def test_not_recovered_half_debt():
    result = estimate_recovery_half_life({
        "events": [
            {"debt": 0.2},
            {"debt": 2.0},
            {"debt": 1.8},
            {"debt": 1.4},
        ]
    })

    assert result["status"] == "NOT_RECOVERED_HALF_DEBT"
