from gvai.kernel.awareness import awareness_state


def test_operational_awareness():
    result = awareness_state(
        heartbeat={"phase": "ELASTIC", "recoverability_state": "RECOVERABLE"},
        vitals={"life_state": "ALIVE_STABLE"},
        belief={"belief_mode": "BELIEVES_AND_RECOVERS"},
        conductor={"conductor_state": "PERFORM"},
    )

    assert result["awareness_mode"] == "SELF_AWARE_OPERATIONAL"
    assert result["can_expand"] is True


def test_critical_awareness_pauses():
    result = awareness_state(
        heartbeat={"phase": "COLLAPSE_ZONE", "recoverability_state": "NON_RECOVERABLE_RISK"},
        vitals={"life_state": "CRITICAL"},
        belief={"belief_mode": "BELIEF_COLLAPSE_RISK"},
        conductor={"conductor_state": "RECOVER"},
    )

    assert result["awareness_mode"] == "SELF_AWARE_CRITICAL"
    assert result["recommended_action"] == "pause_and_restore_reference"
