from datetime import datetime, timezone

from gvai.postlabor.provider_registry import (
    GlobalProviderRegistry,
    ProviderRegistration,
)


class FakeAdapter:
    def __init__(self, configured):
        self.configured = configured


def _registration(country_code, provider, priority, configured, capability="live_job_openings"):
    return ProviderRegistration(
        country_code=country_code,
        provider=provider,
        capability=capability,
        priority=priority,
        attribution=f"{provider} attribution",
        adapter=FakeAdapter(configured),
    )


def test_unsupported_when_no_provider_registered_for_country():
    registry = GlobalProviderRegistry([_registration("US", "usajobs", 1, True)])
    report = registry.capability_report("CA", "live_job_openings")
    assert report.state == "unsupported"
    assert report.providers == ()


def test_authorization_required_when_registered_but_not_configured():
    registry = GlobalProviderRegistry([_registration("US", "usajobs", 1, False)])
    report = registry.capability_report("US", "live_job_openings")
    assert report.state == "authorization_required"
    assert report.providers[0].state == "authorization_required"
    assert report.providers[0].reason is not None


def test_available_when_at_least_one_provider_configured():
    registry = GlobalProviderRegistry([
        _registration("US", "usajobs", 1, False),
        _registration("US", "secondprovider", 2, True),
    ])
    report = registry.capability_report("US", "live_job_openings")
    assert report.state == "available"
    states = {status.provider: status.state for status in report.providers}
    assert states["usajobs"] == "authorization_required"
    assert states["secondprovider"] == "configured"


def test_priority_orders_providers_without_implying_quality():
    registry = GlobalProviderRegistry([
        _registration("US", "second", 2, True),
        _registration("US", "first", 1, True),
    ])
    providers = registry.providers_for("US", "live_job_openings")
    assert [reg.provider for reg in providers] == ["first", "second"]


def test_multiple_countries_are_isolated():
    registry = GlobalProviderRegistry([
        _registration("US", "usajobs", 1, True),
        _registration("CA", "caprovider", 1, True),
    ])
    assert registry.capability_report("US", "live_job_openings").providers[0].provider == "usajobs"
    assert registry.capability_report("CA", "live_job_openings").providers[0].provider == "caprovider"
    assert registry.capability_report("MX", "live_job_openings").state == "unsupported"


def test_temporarily_unavailable_after_failure_and_recovers_after_cooldown():
    clock_time = {"now": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    registry = GlobalProviderRegistry(
        [_registration("US", "usajobs", 1, True)],
        cooldown_seconds=60,
        clock=lambda: clock_time["now"],
    )
    registry.record_failure("US", "usajobs", "live_job_openings")
    report = registry.capability_report("US", "live_job_openings")
    assert report.state == "temporarily_unavailable"
    assert report.providers[0].state == "temporarily_unavailable"

    clock_time["now"] = datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)
    recovered = registry.capability_report("US", "live_job_openings")
    assert recovered.state == "available"


def test_record_success_clears_failure_immediately():
    registry = GlobalProviderRegistry([_registration("US", "usajobs", 1, True)], cooldown_seconds=999)
    registry.record_failure("US", "usajobs", "live_job_openings")
    assert registry.capability_report("US", "live_job_openings").state == "temporarily_unavailable"
    registry.record_success("US", "usajobs", "live_job_openings")
    assert registry.capability_report("US", "live_job_openings").state == "available"


def test_capability_report_never_exposes_adapter_secrets():
    adapter = FakeAdapter(True)
    adapter.api_key = "super-secret-key"
    registration = ProviderRegistration(
        country_code="US",
        provider="usajobs",
        capability="live_job_openings",
        priority=1,
        attribution="USAJOBS API",
        adapter=adapter,
    )
    registry = GlobalProviderRegistry([registration])
    payload = registry.capability_report("US", "live_job_openings").to_dict()
    serialized = str(payload)
    assert "super-secret-key" not in serialized
    assert "api_key" not in serialized
    assert "adapter" not in payload["providers"][0]


def test_invalid_country_code_rejected_on_registration():
    try:
        ProviderRegistration(
            country_code="USA",
            provider="bad",
            capability="live_job_openings",
            priority=1,
            attribution="x",
            adapter=FakeAdapter(True),
        )
        assert False, "expected ValueError"
    except ValueError:
        pass
