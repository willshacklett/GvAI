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


def test_state_county_workforce_mix_uses_single_acs_request(
    monkeypatch,
):
    from gvai.postlabor import region_intel

    monkeypatch.setenv(
        "CENSUS_API_KEY",
        "test-key",
    )

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                [
                    "NAME",
                    "S2401_C01_001E",
                    "S2401_C01_002E",
                    "S2401_C01_018E",
                    "S2401_C01_026E",
                    "S2401_C01_029E",
                    "S2401_C01_033E",
                    "state",
                    "county",
                ],
                [
                    "Alpha County, Tennessee",
                    "1000",
                    "400",
                    "150",
                    "200",
                    "100",
                    "150",
                    "47",
                    "001",
                ],
                [
                    "Beta County, Tennessee",
                    "2000",
                    "500",
                    "300",
                    "400",
                    "300",
                    "500",
                    "47",
                    "003",
                ],
            ]

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(
        region_intel.requests,
        "get",
        fake_get,
    )

    result = (
        region_intel
        .resolve_state_county_workforce_mix(
            "47"
        )
    )

    assert len(calls) == 1
    assert result["supported"] is True
    assert result["data_available"] is True
    assert result["count"] == 2

    first = result["counties"][0]

    assert first["geoid"] == "47001"
    assert (
        first["civilian_employed_16_plus"]
        == 1000.0
    )
    assert (
        first["groups"]
        ["management_business_science_arts"]
        ["share_percent"]
        == 40.0
    )
    assert (
        first["groups"]
        ["service"]
        ["share_percent"]
        == 15.0
    )


def test_workforce_mix_endpoint_requires_state():
    import gvai.api_service as api_service

    client = api_service.app.test_client()

    response = client.get(
        "/api/region/workforce-mix"
    )

    assert response.status_code == 400
    assert (
        response.get_json()["supported"]
        is False
    )


def test_workforce_mix_endpoint_returns_batch(
    monkeypatch,
):
    import gvai.api_service as api_service

    monkeypatch.setattr(
        api_service,
        "resolve_state_county_workforce_mix",
        lambda state_fips: {
            "supported": True,
            "data_available": True,
            "state_fips": state_fips,
            "count": 1,
            "counties": [
                {
                    "geoid": "47037",
                    "groups": {
                        "service": {
                            "share_percent": 17.5,
                        }
                    },
                }
            ],
        },
    )

    client = api_service.app.test_client()

    response = client.get(
        "/api/region/workforce-mix"
        "?state=47"
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["state_fips"] == "47"
    assert payload["count"] == 1
    assert (
        payload["counties"][0]
        ["groups"]["service"]
        ["share_percent"]
        == 17.5
    )


def test_main_globe_contains_workforce_mix_overlay():
    html = (ROOT / "web/index.html").read_text()

    assert "loadTennesseeWorkforceMixOverlay" in html
    assert "/api/region/workforce-mix?state=47" in html
    assert "tennesseeWorkforceMixDataSource" in html
    assert "workforceMixByGeoid" in html
    assert "workforceMixColor" in html
    assert "labor-map-mode" in html
    assert "workforce-group-select" in html
    assert "Workforce Mix" in html
    assert "management_business_science_arts" in html
    assert "production_transportation_material_moving" in html


def test_state_county_housing_pressure_uses_single_acs_request(
    monkeypatch,
):
    from gvai.postlabor import region_intel

    monkeypatch.setenv(
        "CENSUS_API_KEY",
        "test-key",
    )

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                [
                    "NAME",
                    "B19013_001E",
                    "B25077_001E",
                    "state",
                    "county",
                ],
                [
                    "Alpha County, Tennessee",
                    "50000",
                    "200000",
                    "47",
                    "001",
                ],
                [
                    "Beta County, Tennessee",
                    "80000",
                    "240000",
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
        .resolve_state_county_housing_pressure(
            "47"
        )
    )

    assert len(calls) == 1
    assert result["supported"] is True
    assert result["data_available"] is True
    assert result["count"] == 2

    first = result["counties"][0]

    assert first["geoid"] == "47001"
    assert (
        first["median_household_income"]
        == 50000.0
    )
    assert (
        first["median_home_value"]
        == 200000.0
    )
    assert (
        first["home_value_income_ratio"]
        == 4.0
    )

    second = result["counties"][1]

    assert (
        second["home_value_income_ratio"]
        == 3.0
    )


def test_housing_pressure_endpoint_requires_state():
    import gvai.api_service as api_service

    client = api_service.app.test_client()

    response = client.get(
        "/api/region/housing-pressure"
    )

    assert response.status_code == 400
    assert (
        response.get_json()["supported"]
        is False
    )


def test_housing_pressure_endpoint_returns_batch(
    monkeypatch,
):
    import gvai.api_service as api_service

    monkeypatch.setattr(
        api_service,
        "resolve_state_county_housing_pressure",
        lambda state_fips: {
            "supported": True,
            "data_available": True,
            "state_fips": state_fips,
            "count": 1,
            "counties": [
                {
                    "geoid": "47037",
                    "median_household_income":
                        75000.0,
                    "median_home_value":
                        300000.0,
                    "home_value_income_ratio":
                        4.0,
                }
            ],
        },
    )

    client = api_service.app.test_client()

    response = client.get(
        "/api/region/housing-pressure"
        "?state=47"
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["state_fips"] == "47"
    assert payload["count"] == 1
    assert (
        payload["counties"][0]
        ["home_value_income_ratio"]
        == 4.0
    )


def test_main_globe_contains_housing_pressure_overlay():
    html = (ROOT / "web/index.html").read_text()

    assert "loadTennesseeHousingPressureOverlay" in html
    assert "/api/region/housing-pressure?state=47" in html
    assert "tennesseeHousingPressureDataSource" in html
    assert "housingPressureByGeoid" in html
    assert "housingPressureColor" in html
    assert "housing-pressure-legend" in html
    assert "Housing Pressure" in html
    assert 'value="housing"' in html
    assert "home_value_income_ratio" in html


def test_statewide_stex_coverage_requires_state():
    import gvai.api_service as api_service

    client = api_service.app.test_client()

    response = client.get(
        "/api/region/stex-coverage"
    )

    assert response.status_code == 400
    assert (
        response.get_json()["supported"]
        is False
    )


def test_statewide_stex_coverage_rejects_unsupported_state():
    import gvai.api_service as api_service

    client = api_service.app.test_client()

    response = client.get(
        "/api/region/stex-coverage"
        "?state=01"
    )

    assert response.status_code == 400

    payload = response.get_json()

    assert payload["supported"] is False
    assert payload["state_fips"] == "01"


def test_statewide_stex_coverage_maps_counties_to_oews_areas(
    monkeypatch,
):
    import gvai.api_service as api_service

    class FakeEstimate:
        def __init__(
            self,
            area_code,
            occupation_code,
            employment,
            *,
            title=None,
            year=2025,
        ):
            self.area_code = area_code
            self.occupation_code = (
                occupation_code
            )
            self.employment = employment
            self.occupation_title = title
            self.year = year
            self.series_id = "test"
            self.source = "test"
            self.catalog_source = None

    class FakeClient:
        def fetch_catalog_regional_employment(
            self,
            *,
            area_code,
            source_year=None,
        ):
            total = FakeEstimate(
                area_code,
                "00-0000",
                100000,
                year=source_year or 2025,
            )

            rows = [
                FakeEstimate(
                    area_code,
                    "37-2021",
                    1000,
                    title="Pest Control Workers",
                    year=source_year or 2025,
                )
            ]

            return total, rows

    monkeypatch.setattr(
        api_service,
        "OEWSClient",
        lambda: FakeClient(),
    )

    monkeypatch.setattr(
        api_service,
        "list_occupation_stex_profiles",
        lambda: [
            {
                "occupation_code":
                    "37-2021.00",
                "occupation_title":
                    "Pest Control Workers",
                "structural_exposure":
                    50.0,
                "review_status":
                    "approved",
            }
        ],
    )

    client = api_service.app.test_client()

    response = client.get(
        "/api/region/stex-coverage"
        "?state=47&year=2025"
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["supported"] is True
    assert payload["count"] == 95
    assert payload["area_count"] == 14

    first = payload["counties"][0]

    assert first["geoid"] == "47001"
    assert first["oews_area_code"] == "0028940"
    assert first["coverage_percentage"] == 1.0

    assert (
        payload["methodology"]
        ["regional_automation_score"]
        is None
    )

    assert (
        payload["methodology"]
        ["missing_stex_treatment"]
        == "unknown, not zero"
    )


def test_main_globe_contains_stex_coverage_overlay():
    html = (ROOT / "web/index.html").read_text()

    assert "loadTennesseeSTEXCoverageOverlay" in html
    assert "/api/region/stex-coverage?state=47&year=2025" in html
    assert "tennesseeSTEXCoverageDataSource" in html
    assert "stexCoverageByGeoid" in html
    assert "stexCoverageColor" in html
    assert "stex-coverage-legend" in html
    assert 'value="stex"' in html
    assert "STEX Coverage" in html
    assert "Coverage is not automation risk." in html
    assert "Missing STEX is unknown, not zero." in html
