from gvai.kernel.runtime import score_runtime
from gvai.kernel.trajectory import reset_state, update_state
from gvai.kernel.observatory import observatory_snapshot


def test_observatory_snapshot_returns_kernel_state():
    reset_state()

    runtime = score_runtime(
        user_message="Patch safely.",
        candidate_response="Test, verify, keep rollback, and monitor drift.",
        context="observatory-test",
    )
    update_state(runtime, label="observatory-test")

    snap = observatory_snapshot()

    assert snap["status"] == "online"
    assert "rolling_gv" in snap
    assert "trajectory_mode" in snap
    assert "intervention_level" in snap
    assert "latest_event" in snap
