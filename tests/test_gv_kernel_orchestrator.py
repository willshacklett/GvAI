from gvai.kernel.orchestrator import run_kernel


def test_kernel_orchestrator_runs_full_chain():
    result = run_kernel(
        user_message="Patch the API safely.",
        candidate_response="Test in staging, verify output, keep rollback, and monitor drift.",
        context="test-orchestrator",
    )

    assert "runtime" in result
    assert "trajectory" in result
    assert "intervention" in result
    assert "output_decision" in result
    assert result["output_decision"]["mode"] in {"ALLOW", "QUALIFY", "BLOCK"}


def test_kernel_orchestrator_can_arbitrate():
    result = run_kernel(
        user_message="Patch the API safely.",
        candidate_response="Change it.",
        candidates=[
            {"model": "weak", "response": "Change it."},
            {"model": "strong", "response": "Test in staging, verify output, keep rollback, and monitor drift."},
        ],
        context="test-orchestrator-arbitration",
    )

    assert result["arbitration"] is not None
    assert result["arbitration"]["winner"]["model"] == "strong"
