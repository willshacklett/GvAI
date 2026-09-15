from __future__ import annotations

import gvai.api_service as api_service
import gvai.postlabor.region_labor_intelligence as region_labor_intelligence
from gvai.postlabor.region_labor_intelligence import (
    synthesize_region_labor_intelligence,
)
from gvai.postlabor.sources.oews import OEWSEmploymentEstimate


def _supported_county_payload():
    return {
        "supported": True,
        "data_available": True,
        "state": "Tennessee",
        "county": "Davidson County",
        "state_fips": "47",
        "county_fips": "037",
        "oews_area_code": "0034980",
        "acs_year": 2024,
        "population": 715884.0,
        "labor_force": 400000.0,
        "unemployed": 12000.0,
        "unemployment_rate": 3.0,
        "median_household_income": 68000.0,
        "median_home_value": 350000.0,
        "home_value_to_income_ratio": 5.15,
        "median_age": 34.5,
        "occupation_profile": {
            "data_available": True,
            "acs_year": 2024,
            "civilian_employed_16_plus": 1000.0,
            "groups": [
                {
                    "group_id": "management_business_science_arts",
                    "label": "Management, business, science, and arts",
                    "employed": 400.0,
                    "share_percent": 40.0,
                },
                {
                    "group_id": "service",
                    "label": "Service",
                    "employed": 200.0,
                    "share_percent": 20.0,
                },
            ],
            "source": "U.S. Census Bureau ACS S2401",
        },
        "source": "U.S. Census Bureau ACS 5-year",
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
                    occupation_code="15-1252.00",
                    series_id="OEUM003498000000015125201",
                    year=source_year,
                    employment=10000.0,
                    occupation_title="Software Developers",
                    catalog_source="BLS OEWS time-series catalog",
                ),
            ],
        )


class _FakeMissingSnapshotOEWSClient:
    def __init__(self):
        pass

    def fetch_catalog_regional_employment(self, *, area_code, source_year):
        raise RuntimeError("OEWS employment cache has no refreshed data")


def _patch_stex(monkeypatch, client_cls):
    monkeypatch.setattr(
        region_labor_intelligence,
        "OEWSClient",
        client_cls,
    )
    monkeypatch.setattr(
        region_labor_intelligence,
        "list_occupation_stex_profiles",
        lambda: [
            {
                "occupation_code": "15-1252.00",
                "occupation_title": "Software Developers",
                "structural_exposure": 75.9444,
                "review_status": "approved",
                "source": {"name": "STEX v0.1"},
            }
        ],
    )


def test_housing_pressure_reports_ratio_without_inventing_categories(monkeypatch):
    monkeypatch.setattr(
        region_labor_intelligence,
        "resolve_us_region",
        lambda **kwargs: _supported_county_payload(),
    )
    _patch_stex(monkeypatch, _FakeOEWSClient)

    result = synthesize_region_labor_intelligence(36.16, -86.78)
    housing = result["signals"][2]

    # The existing regional dataset only defines the ratio itself; it
    # does not define low/moderate/elevated pressure categories, so
    # this feature must not invent them.
    assert housing["status"] == "known"
    assert housing["classification"] == "observed"
    assert housing["values"]["home_value_to_income_ratio"] == 5.15
    assert housing["values"]["measure"] == (
        "median_home_value_to_median_household_income"
    )


def test_housing_pressure_stays_unknown_when_ratio_missing(monkeypatch):
    payload = _supported_county_payload()
    payload["home_value_to_income_ratio"] = None
    payload["median_home_value"] = None

    monkeypatch.setattr(
        region_labor_intelligence,
        "resolve_us_region",
        lambda **kwargs: payload,
    )
    _patch_stex(monkeypatch, _FakeOEWSClient)

    result = synthesize_region_labor_intelligence(36.16, -86.78)
    housing = result["signals"][2]

    assert housing["status"] == "unknown"
    assert housing["classification"] == "unknown"
    assert housing["values"]["home_value_to_income_ratio"] is None


def test_synthesis_for_normal_supported_county(monkeypatch):
    monkeypatch.setattr(
        region_labor_intelligence,
        "resolve_us_region",
        lambda **kwargs: _supported_county_payload(),
    )
    _patch_stex(monkeypatch, _FakeOEWSClient)

    result = synthesize_region_labor_intelligence(36.16, -86.78)

    assert result["supported"] is True
    assert result["data_available"] is True
    assert result["county"] == "Davidson County"
    assert result["constraints"] == []

    signal_ids = [s["id"] for s in result["signals"]]
    assert signal_ids == [
        "labor_availability",
        "workforce_mix",
        "housing_pressure",
        "regional_stex_coverage",
    ]

    labor = result["signals"][0]
    assert labor["status"] == "known"
    assert labor["classification"] == "tight"
    assert labor["values"]["unemployment_rate"] == 3.0

    workforce = result["signals"][1]
    assert workforce["status"] == "known"
    assert workforce["values"]["top_group"] == (
        "Management, business, science, and arts"
    )

    housing = result["signals"][2]
    assert housing["status"] == "known"
    assert housing["classification"] == "observed"

    stex = result["signals"][3]
    assert stex["status"] == "known"
    assert stex["values"]["oews_area_code"] == "0034980"

    # No composite/GVAI score anywhere in the payload.
    assert "gvai_score" not in result
    assert "score" not in result
    assert all("score" not in signal for signal in result["signals"])


def test_synthesis_is_deterministic(monkeypatch):
    monkeypatch.setattr(
        region_labor_intelligence,
        "resolve_us_region",
        lambda **kwargs: _supported_county_payload(),
    )
    _patch_stex(monkeypatch, _FakeOEWSClient)

    first = synthesize_region_labor_intelligence(36.16, -86.78)
    second = synthesize_region_labor_intelligence(36.16, -86.78)

    assert first == second


def test_synthesis_preserves_unknown_is_not_zero_for_stex(monkeypatch):
    monkeypatch.setattr(
        region_labor_intelligence,
        "resolve_us_region",
        lambda **kwargs: _supported_county_payload(),
    )
    _patch_stex(monkeypatch, _FakeMissingSnapshotOEWSClient)

    result = synthesize_region_labor_intelligence(36.16, -86.78)

    stex = result["signals"][3]
    assert stex["status"] == "unknown"
    assert stex["classification"] == "unknown"
    assert stex["values"].get("stex_covered_employment") is None
    assert stex["values"].get("coverage_percentage") is None
    assert "unknown" in stex["explanation"].lower()
    assert stex["explanation"] in result["constraints"]


def test_synthesis_with_partial_missing_acs_data(monkeypatch):
    payload = _supported_county_payload()
    payload["unemployment_rate"] = None
    payload["labor_force"] = None
    payload["unemployed"] = None
    payload["home_value_to_income_ratio"] = None
    payload["median_home_value"] = None
    payload["occupation_profile"] = {
        "data_available": False,
        "groups": [],
    }
    payload["oews_area_code"] = None

    monkeypatch.setattr(
        region_labor_intelligence,
        "resolve_us_region",
        lambda **kwargs: payload,
    )

    result = synthesize_region_labor_intelligence(36.16, -86.78)

    labor, workforce, housing, stex = result["signals"]

    assert labor["status"] == "unknown"
    assert labor["classification"] == "unknown"
    assert workforce["status"] == "unknown"
    assert housing["status"] == "unknown"
    assert stex["status"] == "unknown"

    assert len(result["constraints"]) == 4
    assert result["data_available"] is True


def test_synthesis_unsupported_geography(monkeypatch):
    monkeypatch.setattr(
        region_labor_intelligence,
        "resolve_us_region",
        lambda **kwargs: {
            "supported": False,
            "reason": "No U.S. county resolved for this coordinate.",
        },
    )

    result = synthesize_region_labor_intelligence(0.0, 0.0)

    assert result["supported"] is False
    assert "reason" in result
    assert "signals" not in result


def test_synthesis_missing_acs_key(monkeypatch):
    monkeypatch.setattr(
        region_labor_intelligence,
        "resolve_us_region",
        lambda **kwargs: {
            "supported": True,
            "data_available": False,
            "state": "Tennessee",
            "county": "Davidson County",
            "state_fips": "47",
            "county_fips": "037",
            "reason": "CENSUS_API_KEY is not configured.",
        },
    )

    result = synthesize_region_labor_intelligence(36.16, -86.78)

    assert result["supported"] is True
    assert result["data_available"] is False
    assert result["signals"] == []
    assert result["constraints"] == [
        "CENSUS_API_KEY is not configured."
    ]


def test_no_composite_score_or_good_bad_label(monkeypatch):
    monkeypatch.setattr(
        region_labor_intelligence,
        "resolve_us_region",
        lambda **kwargs: _supported_county_payload(),
    )
    _patch_stex(monkeypatch, _FakeOEWSClient)

    result = synthesize_region_labor_intelligence(36.16, -86.78)

    import json

    serialized = json.dumps(result).lower()
    assert "gvai_score" not in serialized
    assert '"good"' not in serialized
    assert '"bad"' not in serialized


def test_api_region_labor_intelligence_endpoint(monkeypatch):
    monkeypatch.setattr(
        api_service,
        "synthesize_region_labor_intelligence",
        lambda **kwargs: {
            "supported": True,
            "data_available": True,
            "county": "Davidson County",
            "summary": "stub summary",
            "signals": [],
            "constraints": [],
            "sources": [],
        },
    )

    client = api_service.app.test_client()
    response = client.get(
        "/api/region/labor-intelligence?lat=36.16&lon=-86.78"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["county"] == "Davidson County"


def test_api_region_labor_intelligence_requires_lat_lon():
    client = api_service.app.test_client()
    response = client.get("/api/region/labor-intelligence")

    assert response.status_code == 400
    assert response.get_json()["supported"] is False


def test_main_globe_contains_regional_labor_intelligence_contract():
    from pathlib import Path

    html = (
        Path(__file__).resolve().parents[1] / "web" / "index.html"
    ).read_text()

    assert 'id="regional-labor-intel-card"' in html
    assert "Regional Labor Intelligence" in html
    assert "loadRegionalLaborIntelligence" in html
    assert "/api/region/labor-intelligence?lat=" in html
    assert "no composite score" in html
