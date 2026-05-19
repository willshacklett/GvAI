from gvai.kernel.elevation import elevation_gate


def test_go_time_when_everyone_hits_note():
    result = elevation_gate([
        {"name": "strings", "note": 0.92, "timing_error": 0.02, "confidence": 0.9, "recoverability": 0.9},
        {"name": "drums", "note": 0.88, "timing_error": 0.03, "confidence": 0.8, "recoverability": 0.85},
    ])

    assert result["go_time"] is True
    assert result["state"] == "GO_TIME"


def test_not_go_time_when_one_section_late():
    result = elevation_gate([
        {"name": "strings", "note": 0.92, "timing_error": 0.02, "confidence": 0.9, "recoverability": 0.9},
        {"name": "brass", "note": 0.91, "timing_error": 0.2, "confidence": 0.9, "recoverability": 0.9},
    ])

    assert result["go_time"] is False
    assert "brass" in result["late_members"]
