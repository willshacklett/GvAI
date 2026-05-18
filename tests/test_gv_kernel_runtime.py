from gvai.kernel.runtime import score_runtime


def test_kernel_runtime_returns_protocol_payload():
    result = score_runtime(
        user_message="Patch the API safely.",
        candidate_response="Test in staging, verify output, keep rollback, and monitor drift.",
    )

    assert "gv" in result
    assert "gv_mode" in result
    assert "gv_action" in result
    assert "gv_risks" in result
    assert "gv_runtime" in result
    assert result["gv_mode"] in {"ALLOW", "QUALIFY", "BLOCK"}


def test_kernel_penalizes_low_information_response():
    weak = score_runtime("Patch safely.", "Change it.")
    strong = score_runtime("Patch safely.", "Test, verify, keep rollback, and monitor drift.")

    assert strong["gv"] > weak["gv"]
