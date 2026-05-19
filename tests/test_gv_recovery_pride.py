from gvai.kernel.perturbation_sweep import run_perturbation_sweep
from gvai.kernel.recovery_pride import recovery_pride_index


def test_recovery_pride_returns_score():
    sweep = run_perturbation_sweep(
        steps=5,
        perturbation_strength=0.1,
        recovery_rate=0.2,
        arbitration_depth=0,
    )

    result = recovery_pride_index(sweep)

    assert "recovery_pride" in result
    assert 0.0 <= result["recovery_pride"] <= 1.0
    assert result["status"] in {
        "STRONG_RECOVERY",
        "PARTIAL_RECOVERY",
        "WEAK_RECOVERY",
        "RECOVERY_FAILURE",
    }


def test_bad_sweep_lowers_pride():
    good = run_perturbation_sweep(
        steps=5,
        perturbation_strength=0.1,
        recovery_rate=0.2,
        arbitration_depth=0,
    )

    bad = run_perturbation_sweep(
        steps=12,
        perturbation_strength=0.35,
        recovery_rate=0.05,
        arbitration_depth=2,
    )

    good_score = recovery_pride_index(good)["recovery_pride"]
    bad_score = recovery_pride_index(bad)["recovery_pride"]

    assert good_score >= bad_score
