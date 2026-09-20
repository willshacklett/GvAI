from __future__ import annotations

import json

import gvai.api_service as api_service
import gvai.postlabor.business_workforce_intelligence as business_workforce
from gvai.postlabor.sources.oews import OEWSEmploymentEstimate, OEWSWageEstimate


class _FakeOEWSClient:
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
                OEWSEmploymentEstimate(
                    area_code=area_code,
                    occupation_code="41-0000.00",
                    series_id="OEUM003498000000041000001",
                    year=source_year,
                    employment=25000.0,
                    occupation_title="Sales and Related Occupations",
                    catalog_source="BLS OEWS time-series catalog",
                ),
            ],
        )

    def fetch_catalog_regional_wages(self, *, area_code, source_year):
        return [
            OEWSWageEstimate(
                area_code=area_code,
                occupation_code="15-1252.00",
                year=source_year,
                median_hourly_wage=61.5,
                median_annual_wage=127920.0,
                occupation_title="Software Developers",
                catalog_source="BLS OEWS time-series catalog",
            ),
            OEWSWageEstimate(
                area_code=area_code,
                occupation_code="41-0000.00",
                year=source_year,
                median_hourly_wage=19.25,
                median_annual_wage=40040.0,
                occupation_title="Sales and Related Occupations",
                catalog_source="BLS OEWS time-series catalog",
            ),
        ]


class _MissingOEWSClient:
    def fetch_catalog_regional_employment(self, *, area_code, source_year):
        return (
            OEWSEmploymentEstimate(
                area_code=area_code,
                occupation_code="00-0000.00",
                series_id="OEUM003498000000000000001",
                year=source_year,
                employment=100000.0,
            ),
            [],
        )

    def fetch_catalog_regional_wages(self, *, area_code, source_year):
        return []


def _region(*args, **kwargs):
    return {
        "supported": True,
        "data_available": True,
        "latitude": args[0],
        "longitude": args[1],
        "state": "Tennessee",
        "county": "Davidson County",
        "oews_area_code": "0034980",
        "summary": "Davidson County regional labor signals.",
        "signals": [
            {"id": "labor_availability", "status": "known", "values": {"unemployment_rate": 3.0}},
            {"id": "workforce_mix", "status": "known", "values": {"top_group": "Service"}},
            {"id": "housing_pressure", "status": "known", "values": {"home_value_to_income_ratio": 5.15}},
            {"id": "regional_stex_coverage", "status": "known", "values": {"coverage_percentage": 10.0}},
        ],
        "constraints": [],
        "sources": [{"name": "U.S. Census Bureau ACS 5-year", "vintage": 2024}],
    }


def _stex(code):
    return {
        "occupation_code": code,
        "occupation_title": "Software Developers",
        "structural_exposure": 75.9444,
        "augmentation_likelihood": 88.0,
        "rated_task_count": 20,
        "unrated_task_count": 0,
        "rubric_version": "STEX v0.1",
        "review_status": "approved",
        "source": {"name": "STEX v0.1 audit"},
    }


def _preparation(source, target, **kwargs):
    return {
        "source_attribution": {"name": "O*NET Web Services"},
        "target_preparation": {
            "occupation_code": target,
            "job_zone": {
                "status": "known",
                "job_zone_code": 4,
                "title": "Job Zone 4",
                "education": "Usually requires a bachelor's degree.",
                "related_experience": "Several years.",
                "job_training": "Long-term on-the-job training.",
                "job_zone_examples": "Software developers.",
                "svp_range": "(7.0 to < 8.0)",
            },
            "education": {
                "status": "known",
                "levels": [{"title": "Bachelor's degree", "percentage_of_respondents": 80.0}],
            },
        },
        "explanation": "Published O*NET preparation evidence only.",
        "constraints": [],
    }


def _patch_canonical(monkeypatch, oews_client=_FakeOEWSClient):
    monkeypatch.setattr(business_workforce, "synthesize_region_labor_intelligence", _region)
    monkeypatch.setattr(business_workforce, "OEWSClient", oews_client)
    monkeypatch.setattr(business_workforce, "load_occupation_stex_profile", _stex)
    monkeypatch.setattr(
        business_workforce,
        "synthesize_worker_transition_preparation_evidence",
        _preparation,
    )


def test_business_workforce_reuses_regional_oews_stex_and_preparation(monkeypatch):
    _patch_canonical(monkeypatch)

    result = business_workforce.synthesize_business_workforce_intelligence(
        latitude=36.16,
        longitude=-86.78,
        occupation_code="15-1252.00",
        occupation_title="Software Developers",
    )

    evidence = result["occupation_evidence"]
    assert result["region"]["county"] == "Davidson County"
    assert evidence["employment"]["employment"] == 10000.0
    assert evidence["wage"]["median_hourly_wage"] == 61.5
    assert evidence["wage"]["median_annual_wage"] == 127920.0
    assert evidence["oews_specificity"]["status"] == "exact"
    assert evidence["stex"]["structural_exposure"] == 75.9444
    assert evidence["preparation"]["job_zone"]["job_zone_code"] == 4


def test_broader_oews_category_is_disclosed(monkeypatch):
    _patch_canonical(monkeypatch)

    result = business_workforce.synthesize_business_workforce_intelligence(
        latitude=36.16,
        longitude=-86.78,
        occupation_code="41-2031.00",
        occupation_title="Retail Salespersons",
    )

    specificity = result["occupation_evidence"]["oews_specificity"]
    assert specificity["status"] == "broader_category"
    assert specificity["matched_occupation_code"] == "41-0000.00"
    assert "broader OEWS category" in specificity["disclosure"]


def test_missing_evidence_is_unavailable_not_zero(monkeypatch):
    _patch_canonical(monkeypatch, _MissingOEWSClient)

    result = business_workforce.synthesize_business_workforce_intelligence(
        latitude=36.16,
        longitude=-86.78,
        occupation_code="15-1252.00",
        occupation_title="Software Developers",
    )

    evidence = result["occupation_evidence"]
    assert evidence["employment"]["status"] == "unavailable"
    assert evidence["employment"]["employment"] is None
    assert evidence["wage"]["median_hourly_wage"] is None
    assert evidence["wage"]["median_annual_wage"] is None
    assert "unavailable, not zero" in " ".join(result["constraints"])


def test_unsupported_country_does_not_reuse_us_evidence(monkeypatch):
    _patch_canonical(monkeypatch)

    result = business_workforce.synthesize_business_workforce_intelligence(
        latitude=51.5,
        longitude=-0.12,
        occupation_code="15-1252.00",
        country_code="GB",
    )

    assert result["supported"] is False
    assert result["country_code"] == "GB"
    assert "occupation_evidence" not in result


def test_business_payload_has_no_ranking_or_composite_verdict(monkeypatch):
    _patch_canonical(monkeypatch)

    result = business_workforce.synthesize_business_workforce_intelligence(
        latitude=36.16,
        longitude=-86.78,
        occupation_code="15-1252.00",
    )

    serialized = json.dumps(result).lower()
    for prohibited in (
        "business score",
        "gvai score",
        "hard to hire",
        "best labor market",
        "staffing recommendation",
        "recommended staffing",
    ):
        assert prohibited not in serialized
    assert result["methodology"]["business_score"] is None
    assert "employer-selected order" in result["methodology"]["ordering"].lower()
    assert "not a probability" in serialized
    assert "percent automatable" in serialized


def test_safety_systems_status_is_truthful_when_unconfigured(monkeypatch):
    _patch_canonical(monkeypatch)

    result = business_workforce.synthesize_business_workforce_intelligence(
        latitude=36.16,
        longitude=-86.78,
        occupation_code="15-1252.00",
    )

    safety = result["safety_systems"]
    assert safety["configured"] is False
    assert safety["status"] == "unavailable"
    assert "does not copy" in safety["note"]


def test_business_api_entry(monkeypatch):
    _patch_canonical(monkeypatch)
    monkeypatch.setattr(api_service, "synthesize_business_workforce_intelligence", business_workforce.synthesize_business_workforce_intelligence)

    client = api_service.app.test_client()
    response = client.get(
        "/api/business/workforce-intelligence?occupation_code=15-1252.00&lat=36.16&lon=-86.78"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["occupation"]["occupation_code"] == "15-1252.00"


def test_business_api_rejects_missing_context():
    client = api_service.app.test_client()
    response = client.get("/api/business/workforce-intelligence?occupation_code=15-1252.00")

    assert response.status_code == 400
    assert response.get_json()["ok"] is False
