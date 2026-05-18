from gvai.kernel.protocol import build_gv_heartbeat
from gvai.kernel.phase_timeline import reset_timeline, update_timeline


def test_phase_timeline_tracks_transition():
    reset_timeline()

    elastic = build_gv_heartbeat(
        runtime={"gv": 0.9},
        debt={"debt": 0.1, "elasticity": 0.99, "debt_velocity": 0.01},
        phase={"phase": "ELASTIC"},
    )

    turbulent = build_gv_heartbeat(
        runtime={"gv": 0.74},
        debt={"debt": 1.2, "elasticity": 0.88, "debt_velocity": 0.33},
        phase={"phase": "TURBULENT"},
    )

    update_timeline(elastic)
    state = update_timeline(turbulent)

    assert state["current_phase"] == "TURBULENT"
    assert state["transition_count"] >= 1
    assert state["phase_counts"]["ELASTIC"] == 1
    assert state["phase_counts"]["TURBULENT"] == 1
