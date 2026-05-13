from experiments.gv_falsification.falsify_gv import SCENARIOS, evaluate


def test_gv_falsification_scenarios_run():
    results = [evaluate(name, maker) for name, maker in SCENARIOS.items()]
    assert len(results) == 4
    assert all("verdict" in r for r in results)


def test_gv_has_at_least_one_break_pressure_case():
    results = [evaluate(name, maker) for name, maker in SCENARIOS.items()]
    verdicts = {r["verdict"] for r in results}
    assert "FAIL_MISSED_COLLAPSE" in verdicts or "FAIL_FALSE_POSITIVE" in verdicts
