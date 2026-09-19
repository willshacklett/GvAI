from datetime import datetime, timezone

from gvai.postlabor.labor_providers import ProviderMetadata
from gvai.postlabor.live_jobs import (
    LiveJobsRegistry,
    PublicJobSearchContext,
)


LIVE_METADATA = ProviderMetadata(
    country_code="US",
    provider="fixture-feed",
    capabilities=frozenset({"live_job_openings"}),
    attribution="Fixture feed for tests",
)


class FixtureProvider:
    metadata = LIVE_METADATA

    def __init__(self, openings):
        self.openings = openings
        self.calls = []

    def list_openings(self, **kwargs):
        self.calls.append(kwargs)
        return self.openings


def test_provider_selection_country_isolated_and_zero_results_distinct():
    provider = FixtureProvider([])
    registry = LiveJobsRegistry([provider])

    assert registry.search(PublicJobSearchContext("US")).status == "available_zero_results"
    assert registry.search(PublicJobSearchContext("CA")).status == "unsupported_country"
    assert provider.calls[0]["country_code"] == "US"


def test_provenance_missing_fields_deduplicate_and_preserve_apply_url():
    opening = {
        "provider_job_id": "42",
        "title": "Warehouse worker",
        "employer": None,
        "location": None,
        "country_code": "US",
        "retrieved_at": "2026-09-19T12:00:00+00:00",
        "source_attribution": "Fixture source",
        "apply_url": "https://source.example/jobs/42",
    }
    provider = FixtureProvider([opening, dict(opening)])
    result = LiveJobsRegistry([provider]).search(PublicJobSearchContext("US"))

    assert result.status == "available_with_results"
    assert result.provider_registered is True
    assert len(result.openings) == 1
    payload = result.openings[0].to_dict()
    assert payload["provider"] == "fixture-feed"
    assert payload["provider_job_id"] == "42"
    assert payload["apply_url"] == "https://source.example/jobs/42"
    assert payload["employer"] is None
    assert payload["compensation"] is None
    assert payload["posted_at"] is None


def test_provider_failure_and_malformed_data_are_explicit():
    failing = FixtureProvider([{"title": "missing required fields"}])
    result = LiveJobsRegistry([failing]).search(PublicJobSearchContext("US"))
    assert result.status == "provider_failure"
    assert result.error_type == "ValueError"


def test_provider_request_contains_public_context_only():
    provider = FixtureProvider([])
    LiveJobsRegistry([provider]).search(PublicJobSearchContext(
        "US", occupation_code="15-1252.00", location="Nashville", latitude=36.1,
        longitude=-86.7, radius=25,
    ))
    request = provider.calls[0]
    assert request["location"] == "Nashville"
    assert "worker_profile" not in request
    assert "wages" not in request
    assert "skills" not in request
    assert "credentials" not in request
    assert "constraints" not in request
    assert "preferences" not in request
    assert "experience" not in request


def test_datetime_normalization_is_json_safe():
    provider = FixtureProvider([{
        "provider_job_id": "1",
        "title": "Role",
        "country_code": "US",
        "retrieved_at": datetime(2026, 9, 19, tzinfo=timezone.utc),
        "source_attribution": "Fixture",
        "apply_url": "https://source.example/1",
    }])
    opening = LiveJobsRegistry([provider]).search(PublicJobSearchContext("US")).openings[0]
    assert opening.to_dict()["retrieved_at"].endswith("+00:00")