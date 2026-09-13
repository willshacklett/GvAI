import json
from pathlib import Path

import pytest

import gvai.api_service as api_service
import gvai.postlabor.sources.bls as bls_module
import gvai.postlabor.sources.oews as oews_module
from gvai.postlabor.sources.oews import OEWSClient
from gvai.postlabor.stex import TaskRatingRecord, aggregate_occupation_stex
from gvai.postlabor.stex.regional import build_regional_stex_proposed_preview
from gvai.postlabor.stex.store import (
    list_occupation_stex_profiles,
    load_occupation_stex_tasks,
)


ROOT = Path(__file__).resolve().parents[2]
OCCUPATIONS = {
    "53-7062.00": ("Laborers and Freight, Stock, and Material Movers, Hand", 14, 13, 1, 56.7879, 3.2538, 33120),
    "35-3023.00": ("Fast Food and Counter Workers", 28, 27, 1, 22.7899, 2.9826, 28680),
    "41-2031.00": ("Retail Salespersons", 24, 24, 0, 34.8163, 3.6462, 28580),
    "29-1141.00": ("Registered Nurses", 27, 27, 0, 27.1862, 3.4712, 25100),
    "11-1021.00": ("General and Operations Managers", 17, 17, 0, 34.2254, 3.6832, 23820),
}


@pytest.mark.parametrize("code, expected", OCCUPATIONS.items())
def test_nashville_profiles_preserve_frozen_tasks_and_aggregates(code, expected):
    title, task_count, rated, unrated, stex, augmentation, _ = expected
    raw = json.loads(
        (ROOT / "data" / "onet" / "raw" / f"{code.replace('.', '_')}.tasks.json").read_text()
    )
    profile = json.loads(
        (ROOT / "data" / "stex" / "occupations" / f"{code.replace('.', '_')}.stex.json").read_text()
    )

    assert raw["task_count"] == task_count
    assert len(load_occupation_stex_tasks(code)) == task_count
    assert profile["occupation_title"] == title
    assert profile["rated_task_count"] == rated
    assert profile["unrated_task_count"] == unrated
    assert profile["structural_exposure"] == stex
    assert profile["augmentation_likelihood"] == augmentation
    assert profile["review_status"] == "proposed"
    assert profile["source"]["tasks_year"] == raw["source"]["tasks_vintage"]["year"]


def test_nashville_profiles_are_discoverable():
    production_profiles = list_occupation_stex_profiles()
    proposed_profiles = list_occupation_stex_profiles(review_status="proposed")

    assert {item["occupation_code"] for item in production_profiles} == {
        "15-1252.00",
        "37-2021.00",
    }
    assert {item["occupation_code"] for item in proposed_profiles} == set(OCCUPATIONS)
    assert all(item["review_status"] == "proposed" for item in proposed_profiles)


def test_existing_profiles_remain_approved():
    profiles = {
        item["occupation_code"]: item
        for item in list_occupation_stex_profiles()
    }

    assert profiles["15-1252.00"]["review_status"] == "approved"
    assert profiles["37-2021.00"]["review_status"] == "approved"


def test_task_aggregation_excludes_unrated_importance():
    rated = TaskRatingRecord.create(
        occupation_code="35-3023.00",
        occupation_title="Fast Food and Counter Workers",
        task_id="rated",
        task_title="Rated task",
        task_category="Core",
        source_importance=80,
        source_name="O*NET Tasks / Incumbent",
        source_year=2025,
        digital_capability=4,
        physical_execution=0,
        human_presence_requirement=0,
        augmentation_likelihood=4,
        scorer_id="test",
        rationale="Deterministic test.",
    )
    unrated = TaskRatingRecord.create(
        occupation_code="35-3023.00",
        occupation_title="Fast Food and Counter Workers",
        task_id="unrated",
        task_title="New task",
        task_category="New",
        source_importance=0,
        source_name="O*NET Tasks / Incumbent",
        source_year=2025,
        digital_capability=0,
        physical_execution=4,
        human_presence_requirement=0,
        augmentation_likelihood=0,
        scorer_id="test",
        rationale="Deterministic test.",
    )

    result = aggregate_occupation_stex([rated, unrated])

    assert result.structural_exposure == 100.0
    assert result.rated_task_count == 1
    assert result.unrated_task_count == 1
    assert result.total_importance_weight == 80.0


def test_nashville_production_endpoint_excludes_proposed_profiles(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("regional request attempted network access")

    monkeypatch.setattr(bls_module.requests, "post", fail_network)
    monkeypatch.setattr(oews_module.requests, "get", fail_network)

    response = api_service.app.test_client().get(
        "/api/stex/regional?area=0034980&year=2025&limit=10"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total_employment"] == 1099300.0
    assert payload["stex_covered_employment"] == 8800.0
    assert payload["coverage_percentage"] == 0.8005
    assert payload["methodology"]["regional_automation_score"] is None
    assert payload["covered_occupation_stex"] == 71.1379
    assert payload["recommended_unaudited_occupations"]
    assert {
        item["soc_code"]
        for item in payload["contributing_audited_occupations"]
    } == {"15-1252.00", "37-2021.00"}


def test_nashville_proposed_preview_is_nonproduction(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("preview attempted network access")

    monkeypatch.setattr(bls_module.requests, "post", fail_network)
    monkeypatch.setattr(oews_module.requests, "get", fail_network)

    client = OEWSClient()
    total, rows = client.fetch_catalog_regional_employment(
        area_code="0034980",
        source_year=2025,
    )
    preview = build_regional_stex_proposed_preview(
        total_employment=total,
        employment_rows=rows,
        profiles=list_occupation_stex_profiles(review_status=None),
        occupation_titles={
            row.occupation_code: row.occupation_title
            for row in rows
            if row.occupation_title
        },
        recommendation_limit=10,
    )

    assert preview["review_status"] == "proposed"
    assert preview["production_eligible"] is False
    assert preview["stex_covered_employment"] == 148100.0
    assert preview["coverage_percentage"] == 13.4722
    assert preview["covered_occupation_stex"] == 38.1709
