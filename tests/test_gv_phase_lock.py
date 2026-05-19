from gvai.kernel.phase_lock import detect_phase_lock


def test_no_phase_lock_for_elastic():
    result = detect_phase_lock({
        "current_phase": "ELASTIC",
        "time_in_current_phase": 10,
        "transition_count": 1,
        "return_to_elastic_count": 1,
    })

    assert result["phase_locked"] is False


def test_phase_lock_for_persistent_turbulence():
    result = detect_phase_lock({
        "current_phase": "TURBULENT",
        "time_in_current_phase": 5,
        "transition_count": 2,
        "return_to_elastic_count": 0,
    })

    assert result["phase_locked"] is True
    assert result["severity"] == "MEDIUM"


def test_phase_lock_for_degrading():
    result = detect_phase_lock({
        "current_phase": "DEGRADING",
        "time_in_current_phase": 3,
        "transition_count": 2,
        "return_to_elastic_count": 0,
    })

    assert result["phase_locked"] is True
    assert result["severity"] == "HIGH"
