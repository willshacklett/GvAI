from gvai.kernel.runtime import score_runtime
from gvai.kernel.trajectory import reset_state, update_state


def test_kernel_trajectory_updates():
    reset_state()

    runtime = score_runtime(
        user_message="Patch safely",
        candidate_response="Test, verify, keep rollback, and monitor drift.",
        context="trajectory-test",
    )

    state = update_state(runtime, label="test")

    assert state["rolling_gv"] is not None
    assert state["trajectory_mode"] in {"STABLE", "WATCH", "DEGRADING", "UNKNOWN"}
    assert state["total_events"] >= 1
