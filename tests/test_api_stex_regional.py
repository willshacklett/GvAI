import pytest

from gvai.postlabor.sources.oews import OEWSEmploymentEstimate
import gvai.api_service as api_service


AREA = "0034980"
YEAR = 2025


class FakeOEWSClient:
    refresh_called = False
    lookup_calls = []

    def __init__(self):
        type(self).lookup_calls = []

    def refresh_catalog_cache(self):
        type(self).refresh_called = True

    def refresh_employment_cache(self, **kwargs):
        type(self).refresh_called = True

    def fetch_catalog_regional_employment(self, *, area_code, source_year):
        type(self).lookup_calls.append((area_code, source_year))
        return (
            OEWSEmploymentEstimate(
                area_code=area_code,
                occupation_code="00-0000.00",
                series_id="OEUM003498000000000000001",
                year=source_year or YEAR,
                employment=100000.0,
            ),
            [
                OEWSEmploymentEstimate(
                    area_code=area_code,
                    occupation_code="15-1252.00",
                    series_id="OEUM003498000000015125201",
                    year=source_year or YEAR,
                    employment=10000.0,
                    occupation_title="Software Developers",
                    catalog_source="BLS OEWS time-series catalog",
                ),
                OEWSEmploymentEstimate(
                    area_code=area_code,
                    occupation_code="35-2012.00",
                    series_id="OEUM003498000000035201201",
                    year=source_year or YEAR,
                    employment=20000.0,
                    occupation_title="Cooks, Institution and Cafeteria",
                    catalog_source="BLS OEWS time-series catalog",
                ),
                OEWSEmploymentEstimate(
                    area_code=area_code,
                    occupation_code="31-1120.00",
                    series_id="OEUM003498000000031112001",
                    year=source_year or YEAR,
                    employment=15000.0,
                    occupation_title="Home Health and Personal Care Aides",
                    catalog_source="BLS OEWS time-series catalog",
                ),
            ],
        )


@pytest.fixture
def client(monkeypatch):
    FakeOEWSClient.refresh_called = False
    monkeypatch.setattr(api_service, "OEWSClient", FakeOEWSClient)
    monkeypatch.setattr(
        api_service,
        "list_occupation_stex_profiles",
        lambda: [
            {
                "occupation_code": "15-1252.00",
                "occupation_title": "Software Developers",
                "structural_exposure": 75.9444,
                "source": {"name": "STEX v0.1"},
            }
        ],
    )
    return api_service.app.test_client()


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        ("", "area"),
        ("area=34980", "area"),
        ("area=003498x", "area"),
        ("area=0034980&year=twenty-five", "year"),
        ("area=0034980&limit=ten", "limit"),
        ("area=0034980&limit=-1", "limit"),
        ("area=0034980&limit=51", "limit"),
    ],
)
def test_regional_stex_rejects_invalid_query(client, query, reason):
    response = client.get("/api/stex/regional" + ("?" + query if query else ""))

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["ok"] is False
    assert reason in payload["reason"]


def test_regional_stex_missing_snapshot_returns_503(monkeypatch):
    class MissingSnapshotClient:
        def fetch_catalog_regional_employment(self, **kwargs):
            raise RuntimeError("local snapshot missing")

    monkeypatch.setattr(api_service, "OEWSClient", MissingSnapshotClient)
    client = api_service.app.test_client()

    response = client.get(
        "/api/stex/regional?area=0034980&year=2025"
    )

    assert response.status_code == 503
    payload = response.get_json()
    assert payload == {
        "ok": False,
        "reason": (
            "Regional OEWS employment data has not been refreshed "
            "for the requested area and year."
        ),
    }


def test_regional_stex_success_uses_local_lookup_and_preserves_methodology(
    client,
):
    response = client.get(
        "/api/stex/regional?area=0034980&year=2025&limit=1"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["area_code"] == AREA
    assert payload["source_year"] == YEAR
    assert payload["total_employment"] == 100000.0
    assert payload["stex_covered_employment"] == 10000.0
    assert payload["coverage_percentage"] == 10.0
    assert payload["covered_occupation_stex"] == 75.9444
    assert [
        item["soc_code"]
        for item in payload["contributing_audited_occupations"]
    ] == ["15-1252.00"]
    assert [
        item["soc_code"]
        for item in payload["recommended_unaudited_occupations"]
    ] == ["35-2012.00"]
    assert payload["recommended_unaudited_occupations"][0][
        "potential_incremental_coverage"
    ] == 20.0
    assert payload["methodology"] == {
        "scope": "covered audited occupations only",
        "covered_occupation_stex_scope": (
            "audited occupations represented in the coverage numerator"
        ),
        "regional_automation_score": None,
        "missing_stex_treatment": "unknown, not zero",
        "coverage_denominator": "BLS OEWS All Occupations employment",
    }
    assert FakeOEWSClient.lookup_calls == [(AREA, YEAR)]
    assert FakeOEWSClient.refresh_called is False


def test_regional_stex_unexpected_processing_error_returns_500(
    monkeypatch,
):
    class BrokenClient:
        def fetch_catalog_regional_employment(self, **kwargs):
            raise ValueError("invalid local data")

    monkeypatch.setattr(api_service, "OEWSClient", BrokenClient)
    client = api_service.app.test_client()

    response = client.get("/api/stex/regional?area=0034980")

    assert response.status_code == 500
    assert response.get_json() == {
        "ok": False,
        "reason": "Regional STEX coverage could not be computed.",
    }
