from __future__ import annotations

import json
from pathlib import Path

import gvai.api_service as api_service
import gvai.postlabor.worker_region_outlook as worker_region_outlook
from gvai.postlabor.sources.oews import OEWSEmploymentEstimate
from gvai.postlabor.sources.onet import OnetRelatedOccupation
from gvai.postlabor.stex.store import STEXProfileNotFound
from gvai.postlabor.worker_region_outlook import (
    InvalidSTEXOccupationCode,
    synthesize_worker_related_occupations,
    synthesize_worker_region_outlook,
)


ROOT = Path(__file__).resolve().parents[1]


def _supported_region_payload(*, data_available=True):
    if not data_available:
        return {
            "supported": True,
            "data_available": False,
            "latitude": 36.16,
            "longitude": -86.78,
            "state": "Tennessee",
            "county": "Davidson County",
            "state_fips": "47",
            "county_fips": "037",
            "acs_year": 2024,
            "summary": (
                "Regional labor intelligence is unavailable because "
                "ACS data could not be retrieved for this county."
            ),
            "signals": [],
            "constraints": ["ACS data is unavailable for this county."],
            "sources": [],
        }

    return {
        "supported": True,
        "data_available": True,
        "latitude": 36.16,
        "longitude": -86.78,
        "state": "Tennessee",
        "county": "Davidson County",
        "state_fips": "47",
        "county_fips": "037",
        "acs_year": 2024,
        "oews_area_code": "0034980",
        "summary": "Davidson County regional labor signals; ...",
        "signals": [],
        "constraints": [],
        "sources": [
            {"name": "U.S. Census Bureau ACS 5-year", "vintage": 2024},
        ],
    }


def _stex_profile():
    return {
        "occupation_code": "37-2021.00",
        "occupation_title": "Pest Control Workers",
        "rated_task_count": 14,
        "unrated_task_count": 1,
        "structural_exposure": 35.6614,
        "augmentation_likelihood": 2.4624,
        "rubric_version": "STEX v0.1",
        "review_status": "approved",
        "source": {"tasks_year": 2026},
    }


class _FakeOEWSClient:
    def __init__(self):
        pass

    def fetch_catalog_regional_employment(self, *, area_code, source_year):
        return (
            OEWSEmploymentEstimate(
                area_code=area_code,
                occupation_code="00-0000.00",
                series_id="OEUM003498000000000000001",
                year=source_year,
                employment=100000.0,
            ),
            [
                OEWSEmploymentEstimate(
                    area_code=area_code,
                    occupation_code="372021",
                    series_id="OEUM003498000000372021001",
                    year=source_year,
                    employment=1250.0,
                    occupation_title="Pest Control Workers",
                    catalog_source="BLS OEWS time-series catalog",
                ),
            ],
        )


class _FakeMissingSnapshotOEWSClient:
    def __init__(self):
        pass

    def fetch_catalog_regional_employment(self, *, area_code, source_year):
        raise RuntimeError("OEWS employment cache has no refreshed data")


class _FakeOnetClient:
    def related_occupations(self, occupation_code):
        return [
            OnetRelatedOccupation("53-7062.00", "Laborers", False),
            OnetRelatedOccupation(
                "37-2021.00",
                "Pest Control Workers",
                True,
            ),
        ]


class _UnavailableOnetClient:
    def related_occupations(self, occupation_code):
        raise RuntimeError("O*NET unavailable")


def test_supported_county_and_supported_occupation(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _supported_region_payload(),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "load_occupation_stex_profile",
        lambda code: _stex_profile(),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "OEWSClient",
        _FakeOEWSClient,
    )

    result = synthesize_worker_region_outlook(36.16, -86.78, "37-2021.00")

    assert result["supported"] is True
    assert result["county"] == "Davidson County"
    assert result["occupation_code"] == "37-2021.00"
    assert result["occupation_title"] == "Pest Control Workers"

    stex = result["occupation"]["stex"]
    assert stex["status"] == "known"
    assert stex["profile"]["structural_exposure"] == 35.6614

    employment = result["occupation"]["regional_employment"]
    assert employment["status"] == "known"
    assert employment["employment"] == 1250.0

    assert "market" not in result["occupation"]


def test_missing_stex_profile_is_unknown_not_zero(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _supported_region_payload(),
    )

    def _not_found(code):
        raise STEXProfileNotFound(f"No STEX occupation profile exists for {code}.")

    monkeypatch.setattr(
        worker_region_outlook,
        "load_occupation_stex_profile",
        _not_found,
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "OEWSClient",
        _FakeMissingSnapshotOEWSClient,
    )

    result = synthesize_worker_region_outlook(36.16, -86.78, "53-7062.00")

    stex = result["occupation"]["stex"]
    assert stex["status"] == "unknown"
    assert stex["profile"] is None
    assert "unknown, not zero" in stex["explanation"]
    assert stex["explanation"] in result["constraints"]

    # unknown-not-zero: absolutely no numeric 0 stand-in anywhere for STEX.
    serialized = json.dumps(stex)
    assert '"structural_exposure": 0' not in serialized


def test_missing_regional_data_still_returns_occupation_facts(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _supported_region_payload(data_available=False),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "load_occupation_stex_profile",
        lambda code: _stex_profile(),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "OEWSClient",
        _FakeMissingSnapshotOEWSClient,
    )

    result = synthesize_worker_region_outlook(36.16, -86.78, "37-2021.00")

    assert result["supported"] is True
    assert result["data_available"] is False
    assert result["occupation"]["stex"]["status"] == "known"

    employment = result["occupation"]["regional_employment"]
    assert employment["status"] == "unknown"
    assert employment["employment"] is None

    assert "ACS data is unavailable for this county." in result["constraints"]


def test_unsupported_coordinate_returns_supported_false(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: {
            "supported": False,
            "reason": "No U.S. county resolved for this coordinate.",
        },
    )

    result = synthesize_worker_region_outlook(0.0, 0.0, "37-2021.00")

    assert result["supported"] is False
    assert result["occupation_code"] == "37-2021.00"
    assert "reason" in result


def test_invalid_occupation_code_raises():
    try:
        synthesize_worker_region_outlook(36.16, -86.78, "not-a-code")
        assert False, "expected InvalidSTEXOccupationCode"
    except InvalidSTEXOccupationCode:
        pass


def test_deterministic_output_for_same_inputs(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _supported_region_payload(),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "load_occupation_stex_profile",
        lambda code: _stex_profile(),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "OEWSClient",
        _FakeOEWSClient,
    )

    first = synthesize_worker_region_outlook(36.16, -86.78, "37-2021.00")
    second = synthesize_worker_region_outlook(36.16, -86.78, "37-2021.00")

    assert first == second


def test_no_composite_score_or_geographic_opportunity(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _supported_region_payload(),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "load_occupation_stex_profile",
        lambda code: _stex_profile(),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "OEWSClient",
        _FakeOEWSClient,
    )

    result = synthesize_worker_region_outlook(36.16, -86.78, "37-2021.00")

    serialized = json.dumps(result).lower()
    assert "gvai_score" not in serialized
    assert "composite" not in serialized
    assert "geographic_opportunity" not in serialized
    assert '"good"' not in serialized
    assert '"bad"' not in serialized


def test_related_occupations_preserve_source_order_and_facts(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _supported_region_payload(),
    )

    def load_profile(code):
        if code == "37-2021.00":
            return _stex_profile()
        raise STEXProfileNotFound(code)

    monkeypatch.setattr(
        worker_region_outlook,
        "load_occupation_stex_profile",
        load_profile,
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "OEWSClient",
        _FakeOEWSClient,
    )

    result = synthesize_worker_related_occupations(
        36.16,
        -86.78,
        "37-2021.00",
        onet_client=_FakeOnetClient(),
    )

    items = result["related_occupations"]["items"]
    assert [item["occupation_code"] for item in items] == [
        "53-7062.00",
        "37-2021.00",
    ]
    assert items[0]["stex"]["status"] == "unknown"
    assert items[0]["stex"]["profile"] is None
    assert items[1]["stex"]["status"] == "known"
    assert items[0]["regional_employment"]["status"] == "unknown"
    assert items[0]["regional_employment"]["employment"] is None
    assert items[1]["regional_employment"]["employment"] == 1250.0
    assert items[1]["relationship_metadata"] == {
        "bright_outlook": True,
    }
    assert "re-rank" in result["related_occupations"]["explanation"]

    serialized = json.dumps(result).lower()
    prohibited = (
        "transition_score",
        "career_adjacency",
        "geographic_opportunity",
        "skill_transferability",
        "demand_outlook",
        "wage_retention",
        "retraining_burden",
        "automation_displacement_pressure",
        "confidence",
        "composite",
    )
    assert not any(field in serialized for field in prohibited)
    assert '"structural_exposure": 0' not in serialized


def test_related_occupations_unavailable_is_explicit(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _supported_region_payload(),
    )

    result = synthesize_worker_related_occupations(
        36.16,
        -86.78,
        "37-2021.00",
        onet_client=_UnavailableOnetClient(),
    )

    assert result["related_occupations"]["status"] == "unavailable"
    assert result["related_occupations"]["items"] == []


class _HTTPErrorOnetClient:
    def related_occupations(self, occupation_code):
        import requests

        response = requests.Response()
        response.status_code = 503
        raise requests.HTTPError("upstream failure", response=response)


def test_related_occupations_failure_logs_safely_without_leaking_secrets(
    monkeypatch, caplog
):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _supported_region_payload(),
    )
    monkeypatch.setenv("ONET_API_KEY", "super-secret-onet-key")

    with caplog.at_level("WARNING", logger=worker_region_outlook.__name__):
        result = synthesize_worker_related_occupations(
            36.16,
            -86.78,
            "37-2021.00",
            onet_client=_HTTPErrorOnetClient(),
        )

    # Public API response is unchanged and carries no diagnostic details.
    assert result["related_occupations"]["status"] == "unavailable"
    assert result["related_occupations"]["items"] == []
    serialized_result = json.dumps(result)
    assert "HTTPError" not in serialized_result
    assert "503" not in serialized_result
    assert "super-secret-onet-key" not in serialized_result

    # A safe diagnostic log entry was emitted.
    assert len(caplog.records) == 1
    log_message = caplog.records[0].getMessage()
    assert "HTTPError" in log_message
    assert "api-v2.onetcenter.org" in log_message
    assert "37-2021.00" in log_message
    assert "503" in log_message

    # Secrets, headers, and full URLs are never logged.
    assert "super-secret-onet-key" not in log_message
    assert "ONET_API_KEY" not in log_message
    assert "authorization" not in log_message.lower()
    assert "x-api-key" not in log_message.lower()
    assert "https://" not in log_message


def test_related_occupations_is_deterministic_with_fixed_sources(monkeypatch):
    monkeypatch.setattr(
        worker_region_outlook,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _supported_region_payload(),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "load_occupation_stex_profile",
        lambda code: _stex_profile(),
    )
    monkeypatch.setattr(
        worker_region_outlook,
        "OEWSClient",
        _FakeOEWSClient,
    )

    first = synthesize_worker_related_occupations(
        36.16,
        -86.78,
        "37-2021.00",
        onet_client=_FakeOnetClient(),
    )
    second = synthesize_worker_related_occupations(
        36.16,
        -86.78,
        "37-2021.00",
        onet_client=_FakeOnetClient(),
    )

    assert first == second


# --- API endpoint tests -----------------------------------------------


def test_api_worker_region_outlook_requires_occupation():
    client = api_service.app.test_client()
    response = client.get("/api/worker/region-outlook?lat=36.16&lon=-86.78")

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_worker_region_outlook_requires_lat_lon():
    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/region-outlook?occupation=37-2021.00"
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_worker_region_outlook_invalid_occupation_code():
    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/region-outlook?lat=36.16&lon=-86.78&occupation=bogus"
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_worker_region_outlook_success(monkeypatch):
    monkeypatch.setattr(
        api_service,
        "synthesize_worker_region_outlook",
        lambda **kwargs: {
            "supported": True,
            "data_available": True,
            "county": "Davidson County",
            "occupation_code": "37-2021.00",
            "occupation_title": "Pest Control Workers",
            "occupation": {
                "stex": {"status": "known", "profile": _stex_profile()},
                "regional_employment": {"status": "unknown", "employment": None},
            },
            "worker_outlook": {"summary": "stub summary"},
            "constraints": [],
            "sources": [],
        },
    )

    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/region-outlook?lat=36.16&lon=-86.78&occupation=37-2021.00"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["county"] == "Davidson County"
    assert payload["occupation"]["regional_employment"]["employment"] is None


def test_api_worker_region_outlook_does_not_mutate_existing_endpoints():
    client = api_service.app.test_client()

    stex_catalog = client.get("/api/stex/occupations")
    assert stex_catalog.status_code == 200

    region = client.get("/api/region")
    assert region.status_code in (200, 400, 500)


def test_api_related_occupations_validation_and_success(monkeypatch):
    client = api_service.app.test_client()

    assert client.get(
        "/api/worker/related-occupations?lat=36.16&lon=-86.78"
    ).status_code == 400
    assert client.get(
        "/api/worker/related-occupations?occupation=37-2021.00"
    ).status_code == 400
    assert client.get(
        "/api/worker/related-occupations?lat=36.16&lon=-86.78"
        "&occupation=bogus"
    ).status_code == 400

    monkeypatch.setattr(
        api_service,
        "synthesize_worker_related_occupations",
        lambda **kwargs: {
            "supported": True,
            "related_occupations": {"status": "known", "items": []},
        },
    )

    response = client.get(
        "/api/worker/related-occupations?lat=36.16&lon=-86.78"
        "&occupation=37-2021.00"
    )

    assert response.status_code == 200
    assert response.get_json()["related_occupations"]["status"] == "known"


# --- UI contract tests ---------------------------------------------------


def test_main_globe_contains_worker_outlook_contract():
    html = (ROOT / "web/index.html").read_text()

    assert 'id="stex-occupation-select"' in html
    assert 'id="worker-outlook-btn"' in html
    assert 'id="worker-outlook-card"' in html
    assert 'id="worker-outlook-status"' in html
    assert 'id="worker-outlook-content"' in html
    assert "/api/worker/region-outlook?lat=" in html
    assert "no composite score" in html


def test_main_globe_worker_outlook_precedes_detailed_stex_audit():
    html = (ROOT / "web/index.html").read_text()

    assert html.index('id="stex-occupation-name"') < html.index(
        'id="worker-outlook-btn"'
    )
    assert html.index('id="worker-outlook-btn"') < html.index(
        'id="worker-outlook-card"'
    )
    assert html.index('id="worker-outlook-card"') < html.index(
        'id="stex-task-audit"'
    )
    assert html.index('id="stex-task-audit"') < html.index(
        'id="stex-contributors-list"'
    )


def test_main_globe_detailed_stex_audit_is_collapsible_and_present():
    html = (ROOT / "web/index.html").read_text()

    assert '<details id="stex-task-audit"' in html
    assert "<summary>View detailed STEX task audit</summary>" in html
    assert "Top task contributors" in html
    assert 'id="stex-contributors-list"' in html
    assert '<details id="stex-task-audit" class="stex-audit-disclosure">' in html
    assert '<details id="stex-task-audit" class="stex-audit-disclosure" open>' not in html


def test_main_globe_compact_stex_summary_contract():
    html = (ROOT / "web/index.html").read_text()

    assert 'id="stex-occupation-name"' in html
    assert 'id="stex-occupation-code"' in html
    assert 'id="stex-score"' in html
    assert 'id="stex-rated"' in html
    assert 'id="stex-source-year"' in html
    assert "Structural task exposure under the GVAI STEX methodology." in html
    assert "not a probability of job loss or percent automatable" in html


def test_main_globe_worker_outlook_requires_region_and_occupation():
    html = (ROOT / "web/index.html").read_text()

    assert "currentRegionLatitude" in html
    assert "currentOccupationCode" in html
    assert "renderWorkerOutlookAvailability" in html
    assert "button.disabled = !ready" in html


def test_main_globe_worker_outlook_clears_on_selection_change():
    html = (ROOT / "web/index.html").read_text()

    assert "clearWorkerOutlook()" in html
    # Worker outlook must be cleared both on occupation change and on
    # region change so stale data cannot linger on screen.
    assert html.count("clearWorkerOutlook();") >= 2


def test_main_globe_related_occupations_contract_and_order():
    html = (ROOT / "web/index.html").read_text()

    assert 'id="related-occupations-btn"' in html
    assert 'id="related-occupations-card"' in html
    assert "/api/worker/related-occupations?lat=" in html
    assert "O*NET Related Occupations" in html
    assert "not recommending a job change" in html
    assert "does not re-rank the source results" in html
    assert html.index('id="worker-outlook-card"') < html.index(
        'id="related-occupations-card"'
    )
    assert "clearRelatedOccupations();" in html


def test_main_globe_regional_labor_intelligence_contract_still_present():
    html = (ROOT / "web/index.html").read_text()

    assert 'id="regional-labor-intel-card"' in html
    assert "loadRegionalLaborIntelligence" in html
    assert "/api/region/labor-intelligence?lat=" in html


def test_main_globe_regional_stex_contract_still_present():
    html = (ROOT / "web/index.html").read_text()

    assert 'id="regional-stex-card"' in html
    assert "loadRegionalSTEX" in html
    assert "/api/stex/regional?area=" in html
