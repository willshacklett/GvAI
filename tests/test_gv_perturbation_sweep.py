from gvai.kernel.perturbation_sweep import run_perturbation_sweep


def test_perturbation_sweep_runs():
    result = run_perturbation_sweep(
        steps=5,
        perturbation_strength=0.2,
        recovery_rate=0.1,
        arbitration_depth=1,
    )

    assert result["steps"] == 5
    assert len(result["events"]) == 5
    assert "phase_lock" in result
    assert "recovery_half_life" in result


def test_arbitration_depth_affects_masking_distance():
    shallow = run_perturbation_sweep(
        steps=5,
        perturbation_strength=0.25,
        recovery_rate=0.1,
        arbitration_depth=0,
    )

    deep = run_perturbation_sweep(
        steps=5,
        perturbation_strength=0.25,
        recovery_rate=0.1,
        arbitration_depth=3,
    )

    shallow_last = shallow["events"][-1]["masking_distance"]
    deep_last = deep["events"][-1]["masking_distance"]

    assert deep_last >= shallow_last
