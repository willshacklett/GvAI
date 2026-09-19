from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone
from inspect import signature
from pathlib import Path

import gvai.postlabor.worker_region_outlook as worker_region_outlook
from gvai.postlabor.labor_providers import (
    LiveJobsProvider,
    NormalizedJobOpening,
    OccupationReference,
    PublishedCompensation,
    US_ONET_OEWS_STEX,
    provider_for_country,
)
from gvai.postlabor.worker_region_outlook import (
    synthesize_worker_region_outlook,
)


def test_us_provider_preserves_existing_evidence_capabilities():
    assert provider_for_country(None) == US_ONET_OEWS_STEX
    assert US_ONET_OEWS_STEX.supports("occupation_profiles")
    assert US_ONET_OEWS_STEX.supports("employment")
    assert US_ONET_OEWS_STEX.supports("wages")
    assert US_ONET_OEWS_STEX.supports("preparation")
    assert US_ONET_OEWS_STEX.supports("structural_exposure")
    assert not US_ONET_OEWS_STEX.supports("live_job_openings")


def test_unsupported_country_never_falls_back_to_us_evidence(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("U.S. evidence must not be queried")
        ),
    )

    result = synthesize_worker_region_outlook(
        43.65, -79.38, "NOC-21231", country_code="CA"
    )

    assert result["supported"] is False
    assert result["occupation_code"] == "NOC-21231"
    assert result["occupation"]["regional_employment"]["status"] == "unavailable"
    assert result["occupation"]["regional_employment"]["value"] is None
    assert "not substituted" in result["reason"]


def test_worker_routes_gate_unsupported_countries_before_us_synthesis():
    source = (Path(__file__).resolve().parents[1] / "gvai/api_service.py").read_text()
    for route in (
        "api_worker_region_outlook",
        "api_worker_related_occupations",
        "api_worker_transition_evidence",
        "api_worker_transition_preparation",
        "api_worker_transition_action_plan",
    ):
        start = source.index(f"def {route}")
        next_route = source.find("\n@app.", start + 1)
        body = source[start:next_route if next_route != -1 else None]
        assert "_unsupported_worker_country_response" in body


def test_occupation_reference_retains_source_namespace_and_missing_crosswalk():
    reference = OccupationReference(
        country_code="US",
        provider="us_onet_oews_stex",
        provider_occupation_code="37-2021.00",
        title="Pest Control Workers",
    )

    assert reference.provider_occupation_code == "37-2021.00"
    assert reference.international_identifier is None
    assert reference.to_dict()["international_identifier"] is None


def test_normalized_job_opening_preserves_provider_provenance():
    reference = OccupationReference(
        country_code="US",
        provider="us_onet_oews_stex",
        provider_occupation_code="15-1252.00",
        title="Software Developers",
    )
    opening = NormalizedJobOpening(
        provider="authorized-feed",
        provider_job_id="job-42",
        title="Software Developer",
        employer="Example Employer",
        location="Nashville, TN",
        country_code="US",
        retrieved_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
        source_attribution="Example Authorized Feed",
        apply_url="https://jobs.example.test/apply/job-42",
        occupation=reference,
        compensation=PublishedCompensation(amount=42.0, currency="USD", interval="hour"),
    )

    payload = opening.to_dict()
    assert payload["provider"] == "authorized-feed"
    assert payload["provider_job_id"] == "job-42"
    assert payload["source_attribution"] == "Example Authorized Feed"
    assert payload["apply_url"] == "https://jobs.example.test/apply/job-42"
    assert payload["occupation"]["provider_occupation_code"] == "15-1252.00"
    assert payload["remote_or_hybrid"] is None
    assert payload["posted_at"] is None


def test_jobs_contract_has_no_ranking_or_worker_profile_input():
    field_names = {field.name for field in fields(NormalizedJobOpening)}
    assert not field_names & {"rank", "score", "fit", "recommendation"}
    parameters = signature(LiveJobsProvider.list_openings).parameters
    assert "worker_profile" not in parameters
    assert "profile" not in parameters