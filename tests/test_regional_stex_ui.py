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
