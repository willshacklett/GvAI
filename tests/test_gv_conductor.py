from gvai.kernel.conductor import conductor_decision


def test_conductor_performs_when_ready():
    result = conductor_decision(
        musicians=[
            {"name": "strings", "note": 0.94, "timing_error": 0.02, "confidence": 0.92, "alignment": 0.95, "recoverability": 0.91},
            {"name": "drums", "note": 0.90, "timing_error": 0.03, "confidence": 0.88, "alignment": 0.84, "recoverability": 0.86},
            {"name": "vocals", "note": 0.96, "timing_error": 0.01, "confidence": 0.94, "alignment": 0.96, "recoverability": 0.93},
        ],
        vitals={"life_state": "ALIVE_STABLE"},
        belief={"belief_mode": "BELIEVES_AND_RECOVERS"},
    )

    assert result["conductor_state"] in {"PERFORM", "GO_TIME"}


def test_vitals_override_performance():
    result = conductor_decision(
        musicians=[
            {"name": "strings", "note": 0.94, "timing_error": 0.02, "confidence": 0.92, "alignment": 0.95, "recoverability": 0.91},
        ],
        vitals={"life_state": "CRITICAL"},
        belief={"belief_mode": "BELIEVES_AND_RECOVERS"},
    )

    assert result["conductor_state"] == "RECOVER"
