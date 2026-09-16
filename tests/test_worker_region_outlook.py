from __future__ import annotations

import json
from pathlib import Path

import gvai.api_service as api_service
import gvai.postlabor.worker_region_outlook as worker_region_outlook
from gvai.postlabor.sources.oews import OEWSEmploymentEstimate
from gvai.postlabor.stex.store import STEXProfileNotFound
from gvai.postlabor.worker_region_outlook import (
    InvalidSTEXOccupationCode,
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
