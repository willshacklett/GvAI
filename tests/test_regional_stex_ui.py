from pathlib import Path

import gvai.api_service as api_service
from gvai.postlabor.region_intel import resolve_packaged_oews_area_code
from gvai.postlabor.sources.oews_geography import (
    TENNESSEE_COUNTY_TO_OEWS_AREA,
)


ROOT = Path(__file__).resolve().parents[1]


def test_all_tennessee_counties_resolve_to_packaged_nonstatewide_areas():
    import json

    snapshot = json.loads(
        (ROOT / "gvai/postlabor/snapshots/oews/employment_index.json").read_text()
    )
    targets = set(snapshot["areas"])

    assert len(TENNESSEE_COUNTY_TO_OEWS_AREA) == 95
    assert set(TENNESSEE_COUNTY_TO_OEWS_AREA.values()) <= targets
    assert "4700000" not in TENNESSEE_COUNTY_TO_OEWS_AREA.values()


def test_packaged_oews_mapping_uses_authoritative_tennessee_assignments():
    assert resolve_packaged_oews_area_code("47", "037") == "0034980"
    assert resolve_packaged_oews_area_code("47", "149") == "0034980"
    assert resolve_packaged_oews_area_code("47", "093") == "0028940"
    assert resolve_packaged_oews_area_code("47", "065") == "0016860"
    assert resolve_packaged_oews_area_code("47", "125") == "0017300"
    assert resolve_packaged_oews_area_code("47", "157") == "0032820"
    assert resolve_packaged_oews_area_code("47", "003") == "4700002"
    assert resolve_packaged_oews_area_code("47", "141") == "4700003"
    assert resolve_packaged_oews_area_code("47", "155") == "4700004"
    assert resolve_packaged_oews_area_code("47", "183") == "4700001"
    assert resolve_packaged_oews_area_code("26", "163") is None
    assert resolve_packaged_oews_area_code("", "") is None


def test_region_payload_exposes_nashville_oews_area(monkeypatch):
    monkeypatch.setattr(
        api_service,
        "resolve_us_region",
        lambda **kwargs: {
            "supported": True,
            "state_fips": "47",
            "county_fips": "037",
            "county": "Davidson County",
        },
    )

    response = api_service.app.test_client().get(
        "/api/region?lat=36.16&lon=-86.78"
    )

    assert response.status_code == 200
    assert response.get_json()["oews_area_code"] == "0034980"


def test_region_payload_exposes_representative_tennessee_oews_areas(monkeypatch):
    client = api_service.app.test_client()
    for county_fips, expected in (("093", "0028940"), ("003", "4700002")):
        monkeypatch.setattr(
            api_service,
            "resolve_us_region",
            lambda **kwargs: {
                "supported": True,
                "state_fips": "47",
                "county_fips": county_fips,
            },
        )
        response = client.get("/api/region?lat=36.16&lon=-86.78")
        assert response.status_code == 200
        assert response.get_json()["oews_area_code"] == expected


def test_main_globe_contains_regional_stex_contract():
    html = (ROOT / "web/index.html").read_text()

    assert 'id="regional-stex-card"' in html
    assert "Regional STEX Coverage" in html
    assert "loadRegionalSTEX" in html
    assert "/api/stex/regional?area=" in html
    assert "STEX across audited covered occupations" in html
    assert "Unrated employment is unknown, not zero." in html
    assert "Next occupations to audit" in html
    assert "activeRegionRequestId" in html
    assert "regional_automation_score" not in html
    assert "review_status" not in html


def test_public_stex_catalog_remains_approved_only():
    response = api_service.app.test_client().get("/api/stex/occupations")

    assert response.status_code == 200
    assert {
        item["occupation_code"]
        for item in response.get_json()["profiles"]
    } == {"15-1252.00", "37-2021.00"}


def test_main_globe_contains_geography_boundary_layer():
    html = (ROOT / "web/index.html").read_text()

    assert "loadUsStateBoundaries" in html
    assert "loadTennesseeCountyBoundaries" in html
    assert "updateGeographyBoundaryVisibility" in html
    assert "GEOGRAPHY_VISIBILITY" in html
    assert "TIGERweb/State_County/MapServer/0/query" in html
    assert "TIGERweb/State_County/MapServer/7/query" in html
    assert "tennesseeCountiesMaxHeight" in html
    assert "viewer.camera.moveEnd.addEventListener" in html


def test_main_globe_contains_global_country_context_layer():
    html = (ROOT / "web/index.html").read_text()

    assert "loadGlobalCountryBoundaries" in html
    assert "globalCountriesDataSource" in html
    assert "countriesMinHeight" in html
    assert "ne_110m_admin_0_countries.geojson" in html

    artifact = (
        ROOT
        / "web/data/geography/ne_110m_admin_0_countries.geojson"
    )

    assert artifact.exists()
    assert artifact.stat().st_size == 838726

def test_labor_availability_classifier():
    from gvai.postlabor.region_intel import (
        classify_labor_availability,
    )

    assert classify_labor_availability(None) == "unknown"
    assert classify_labor_availability(3.4) == "tight"
    assert classify_labor_availability(3.5) == "balanced"
    assert classify_labor_availability(5.5) == "balanced"
    assert classify_labor_availability(5.6) == "available"


def test_state_county_labor_availability_uses_single_acs_request(
    monkeypatch,
):
    from gvai.postlabor import region_intel

    monkeypatch.setenv(
        "CENSUS_API_KEY",
        "test-key",
    )

    calls = []

    class FakeResponse:
        headers = {
            "content-type":
                "application/json"
        }

        def raise_for_status(self):
            return None

        def json(self):
            return [
                [
                    "NAME",
                    "B01003_001E",
                    "B23025_003E",
                    "B23025_005E",
                    "state",
                    "county",
                ],
                [
                    "Alpha County, Tennessee",
                    "1000",
                    "500",
                    "10",
                    "47",
                    "001",
                ],
                [
                    "Beta County, Tennessee",
                    "2000",
                    "1000",
                    "70",
                    "47",
                    "003",
                ],
            ]

    def fake_get(url, **kwargs):
        calls.append(
            (url, kwargs)
        )
        return FakeResponse()

    monkeypatch.setattr(
        region_intel.requests,
        "get",
        fake_get,
    )

    result = (
        region_intel
        .resolve_state_county_labor_availability(
            "47"
        )
    )

    assert len(calls) == 1
    assert result["supported"] is True
    assert result["data_available"] is True
    assert result["count"] == 2

    assert result["counties"][0]["geoid"] == "47001"
    assert (
        result["counties"][0]
        ["unemployment_rate"]
        == 2.0
    )
    assert (
        result["counties"][0]
        ["availability"]
        == "tight"
    )

    assert result["counties"][1]["geoid"] == "47003"
    assert (
        result["counties"][1]
        ["unemployment_rate"]
        == 7.0
    )
    assert (
        result["counties"][1]
        ["availability"]
        == "available"
    )


def test_labor_availability_endpoint_requires_state():
    import gvai.api_service as api_service

    client = api_service.app.test_client()

    response = client.get(
        "/api/region/labor-availability"
    )

    assert response.status_code == 400
    assert (
        response.get_json()["supported"]
        is False
    )


def test_labor_availability_endpoint_returns_batch(
    monkeypatch,
):
    import gvai.api_service as api_service

    monkeypatch.setattr(
        api_service,
        "resolve_state_county_labor_availability",
        lambda state_fips: {
            "supported": True,
            "data_available": True,
            "state_fips": state_fips,
            "count": 1,
            "counties": [
                {
                    "geoid": "47037",
                    "availability":
                        "balanced",
                }
            ],
        },
    )

    client = api_service.app.test_client()

    response = client.get(
        "/api/region/labor-availability"
        "?state=47"
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["state_fips"] == "47"
    assert payload["count"] == 1
    assert (
        payload["counties"][0]
        ["geoid"]
        == "47037"
    )


def test_main_globe_contains_labor_availability_overlay():
    html = (ROOT / "web/index.html").read_text()

    assert "loadTennesseeLaborAvailabilityOverlay" in html
    assert "/api/region/labor-availability?state=47" in html
    assert "laborAvailabilityByGeoid" in html
    assert "laborAvailabilityColor" in html
    assert "labor-availability-legend" in html
    assert "Human Labor Availability" in html
    assert "tennesseeLaborAvailabilityDataSource" in html
