from gvai.postlabor.labor_providers import ProviderMetadata
from gvai.postlabor.live_jobs import LiveJobsRegistry, PublicJobSearchContext
from gvai.postlabor.provider_registry import GlobalProviderRegistry, ProviderRegistration


LIVE_METADATA = ProviderMetadata(
    country_code="US",
    provider="fixture-feed",
    capabilities=frozenset({"live_job_openings"}),
    attribution="Fixture feed for tests",
)


class FixtureProvider:
    metadata = LIVE_METADATA
    configured = True

    def __init__(self, openings=None, error=None):
        self.openings = openings or []
        self.error = error

    def list_openings(self, **kwargs):
        if self.error:
            raise self.error
        return self.openings


def _registry_with(provider, capability_registry):
    return LiveJobsRegistry([provider], capability_registry=capability_registry)


def test_search_failure_marks_provider_temporarily_unavailable_in_registry():
    provider = FixtureProvider(error=RuntimeError("upstream down"))
    capability_registry = GlobalProviderRegistry([
        ProviderRegistration(
            country_code="US",
            provider="fixture-feed",
            capability="live_job_openings",
            priority=1,
            attribution="Fixture feed for tests",
            adapter=provider,
        )
    ])
    result = _registry_with(provider, capability_registry).search(PublicJobSearchContext("US"))
    assert result.status == "provider_failure"

    report = capability_registry.capability_report("US", "live_job_openings")
    assert report.state == "temporarily_unavailable"


def test_search_success_keeps_provider_available_in_registry():
    provider = FixtureProvider(openings=[])
    capability_registry = GlobalProviderRegistry([
        ProviderRegistration(
            country_code="US",
            provider="fixture-feed",
            capability="live_job_openings",
            priority=1,
            attribution="Fixture feed for tests",
            adapter=provider,
        )
    ])
    result = _registry_with(provider, capability_registry).search(PublicJobSearchContext("US"))
    assert result.status == "available_zero_results"

    report = capability_registry.capability_report("US", "live_job_openings")
    assert report.state == "available"


def test_search_without_capability_registry_is_unaffected():
    provider = FixtureProvider(error=RuntimeError("upstream down"))
    result = LiveJobsRegistry([provider]).search(PublicJobSearchContext("US"))
    assert result.status == "provider_failure"


def test_default_registries_are_wired_together():
    from gvai.postlabor.live_jobs import DEFAULT_LIVE_JOBS_REGISTRY, DEFAULT_PROVIDER_REGISTRY

    assert DEFAULT_LIVE_JOBS_REGISTRY._capability_registry is DEFAULT_PROVIDER_REGISTRY
    report = DEFAULT_PROVIDER_REGISTRY.capability_report("US", "live_job_openings")
    assert report.state in {"available", "authorization_required", "temporarily_unavailable"}
    assert report.providers[0].provider == "usajobs"
