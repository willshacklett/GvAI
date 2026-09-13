from pathlib import Path

import gvai.api_service as api_service
from gvai.postlabor.region_intel import resolve_packaged_oews_area_code


ROOT = Path(__file__).resolve().parents[1]


def test_packaged_oews_mapping_only_resolves_supported_nashville_county():
    assert resolve_packaged_oews_area_code("47", "037") == "0034980"
    assert resolve_packaged_oews_area_code("47", "001") is None
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
