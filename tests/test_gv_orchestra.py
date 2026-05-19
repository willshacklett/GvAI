from gvai.kernel.orchestra import orchestra_confidence


def test_building_confidence():
    result = orchestra_confidence([
        {
            "name": "strings",
            "confidence": 0.8,
            "alignment": 0.9,
            "recoverability": 0.8,
        },
        {
            "name": "drums",
            "confidence": 0.7,
            "alignment": 0.75,
            "recoverability": 0.7,
        },
    ])

    assert result["state"] in {
        "BUILDING_CONFIDENCE",
        "FULL_HARMONY",
    }


def test_dissonance_risk():
    result = orchestra_confidence([
        {
            "name": "horns",
            "confidence": 0.2,
            "alignment": 0.3,
            "recoverability": 0.2,
        }
    ])

    assert result["state"] == "DISSONANCE_RISK"
