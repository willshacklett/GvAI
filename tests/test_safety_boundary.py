from gvai.safety_boundary import GovernanceDecision, SafetySystemsBoundary


def test_unconfigured_safety_systems_is_honestly_unavailable():
    decision = SafetySystemsBoundary().decide("submit_application")
    assert decision.status == "unavailable"
    assert decision.configured is False


def test_boundary_passes_future_consequential_action_to_external_decider():
    calls = []

    def decider(action, context):
        calls.append((action, context))
        return GovernanceDecision("warn", "review required", True)

    decision = SafetySystemsBoundary(decider).decide(
        "contact_employer", context={"country_code": "US"}
    )
    assert decision.status == "warn"
    assert calls == [("contact_employer", {"country_code": "US"})]