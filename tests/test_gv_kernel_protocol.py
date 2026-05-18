from gvai.kernel.protocol import (
    build_gv_heartbeat,
    validate_heartbeat,
)


def test_build_heartbeat():

    payload = build_gv_heartbeat(
        runtime={"gv": 0.82},
        debt={
            "debt": 1.2,
            "elasticity": 0.91,
            "debt_velocity": 0.33,
        },
        phase={"phase": "TURBULENT"},
        visible_coherence=0.96,
    )

    assert payload["protocol"] == "GV_RUNTIME_PROTOCOL"

    assert payload["phase"] == "TURBULENT"

    assert payload["recoverability_state"] == "STRESSED"

    assert "masking_distance" in payload


def test_validate_heartbeat():

    payload = build_gv_heartbeat(
        runtime={"gv": 0.9},
        debt={"debt": 0.5},
        phase={"phase": "ELASTIC"},
    )

    result = validate_heartbeat(payload)

    assert result["valid"] is True
