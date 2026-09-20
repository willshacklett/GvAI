from datetime import datetime, timezone

from gvai.postlabor.labor_providers import ProviderMetadata
from gvai.postlabor.live_jobs import LiveJobsRegistry, PublicJobSearchContext
from gvai.postlabor.provider_registry import GlobalProviderRegistry, ProviderRegistration


def _opening(provider, job_id, url, title="Warehouse Worker"):
    return {
        "provider": provider,
        "provider_job_id": job_id,
        "title": title,
        "employer": "Public Employer",
        "location": "Nashville, TN",
        "country_code": "US",
        "retrieved_at": datetime(2026, 9, 20, tzinfo=timezone.utc),
        "source_attribution": f"{provider} API",
        "apply_url": url,
    }


class FixtureProvider:
    configured = True
    supported_search_filters = frozenset({
        "location", "radius", "remote_only", "schedule_type_code", "posted_within_days"
    })

    def __init__(self, name, openings=(), error=None, supported_search_filters=None):
        self.metadata = ProviderMetadata(
            "US", name, frozenset({"live_job_openings"}), f"{name} API"
        )
        self.openings = openings
        self.error = error
        self.calls = []
        if supported_search_filters is not None:
            self.supported_search_filters = frozenset(supported_search_filters)

    def list_openings(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.openings


def _capability_registry(*providers):
    return GlobalProviderRegistry([
        ProviderRegistration(
            country_code="US",
            provider=provider.metadata.provider,
            capability="live_job_openings",
            priority=index,
            attribution=provider.metadata.attribution,
            adapter=provider,
        )
        for index, provider in enumerate(providers, 1)
    ])


def test_multiple_providers_preserve_distinct_similar_openings_and_safe_deduplication():
    first = FixtureProvider("first", [
        _opening("first", "a", "https://jobs.example/opening/1"),
        _opening("first", "a", "https://jobs.example/opening/1"),
        _opening("first", "b", "https://jobs.example/opening/2"),
    ])
    second = FixtureProvider("second", [
        _opening("second", "x", "https://jobs.example/opening/1#details"),
        _opening("second", "y", "https://other.example/opening/9"),
    ])
    result = LiveJobsRegistry(
        [first, second], capability_registry=_capability_registry(first, second)
    ).search(PublicJobSearchContext("US"))

    assert result.status == "available_with_results"
    assert result.providers == ("first", "second")
    assert len(result.openings) == 3
    assert [(ref.provider, ref.provider_job_id) for ref in result.openings[0].provider_references] == [
        ("first", "a"), ("second", "x")
    ]
    assert [opening.provider_job_id for opening in result.openings[1:]] == ["b", "y"]


def test_provider_failure_is_isolated_when_another_provider_succeeds():
    failed = FixtureProvider("failed", error=RuntimeError("down"))
    healthy = FixtureProvider("healthy", [_opening("healthy", "1", "https://jobs.example/1")])
    result = LiveJobsRegistry(
        [failed, healthy], capability_registry=_capability_registry(failed, healthy)
    ).search(PublicJobSearchContext("US"))

    assert result.status == "available_with_results"
    assert result.providers == ("healthy",)
    assert result.provider_failures == ({"provider": "failed", "error_type": "RuntimeError"},)


def test_result_limit_applies_across_multiple_providers(monkeypatch):
    monkeypatch.setenv("GVAI_LIVE_JOBS_RESULT_LIMIT", "2")
    first = FixtureProvider("first", [
        _opening("first", "1", "https://first.example/1"),
        _opening("first", "2", "https://first.example/2"),
    ])
    second = FixtureProvider("second", [
        _opening("second", "3", "https://second.example/3"),
    ])

    result = LiveJobsRegistry([first, second]).search(PublicJobSearchContext("US"))

    assert len(result.openings) == 2
    assert first.calls and second.calls


def test_unsupported_filter_does_not_run_an_unfiltered_search():
    provider = FixtureProvider("limited", supported_search_filters={"location"})
    result = LiveJobsRegistry([provider]).search(
        PublicJobSearchContext("US", remote_only=True)
    )

    assert result.status == "unsupported_filters"
    assert result.unsupported_filters == ("remote_only",)
    assert provider.calls == []


def test_selected_filters_are_forwarded_without_private_profile_data():
    provider = FixtureProvider("full")
    context = PublicJobSearchContext(
        "US", location="Nashville", radius=30, remote_only=False,
        schedule_type_code="2", posted_within_days=14,
    )
    LiveJobsRegistry([provider]).search(context)

    request = provider.calls[0]
    assert request["location"] == "Nashville"
    assert request["radius"] == 30
    assert request["remote_only"] is False
    assert request["schedule_type_code"] == "2"
    assert request["posted_within_days"] == 14
    assert not ({"worker_profile", "wage", "education", "experience", "credentials", "skills", "preferences"} & set(request))


def test_registered_unconfigured_and_cooling_down_states_are_explicit():
    provider = FixtureProvider("fixture")
    provider.configured = False
    registry = _capability_registry(provider)
    unavailable = LiveJobsRegistry([], capability_registry=registry).search(PublicJobSearchContext("US"))
    assert unavailable.status == "authorization_required"

    provider.configured = True
    registry.record_failure("US", "fixture", "live_job_openings")
    cooling = LiveJobsRegistry([provider], capability_registry=registry).search(PublicJobSearchContext("US"))
    assert cooling.status == "temporarily_unavailable"
    assert provider.calls == []