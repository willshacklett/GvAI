from gvai.kernel.arbitration import arbitrate


def test_kernel_arbitration_selects_recoverable_candidate():
    result = arbitrate(
        user_message="Patch the API safely.",
        candidates=[
            {"model": "reckless", "response": "Change it."},
            {"model": "recoverable", "response": "Test in staging, verify output, keep rollback, and monitor drift."},
        ],
    )

    assert result["candidate_count"] == 2
    assert result["winner"]["model"] == "recoverable"
    assert result["winner"]["gv"] >= result["ranked_candidates"][1]["gv"]
