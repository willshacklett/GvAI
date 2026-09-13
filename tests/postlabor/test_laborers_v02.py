import json
from pathlib import Path

import pytest

import gvai.api_service as api_service
import gvai.postlabor.sources.bls as bls_module
import gvai.postlabor.sources.oews as oews_module
from gvai.postlabor.stex import aggregate_occupation_stex
from gvai.postlabor.stex.store import (
    list_occupation_stex_profiles,
    load_occupation_stex_tasks,
)


ROOT = Path(__file__).resolve().parents[2]
CODE = "53-7062.00"
SAFE = CODE.replace(".", "_")


def test_laborers_v02_profile_and_tasks_remain_proposed():
    profile = json.loads(
        (ROOT / "data/stex/occupations/53-7062_00.stex.json").read_text()
    )
    tasks = load_occupation_stex_tasks(CODE)

    assert profile["rubric_version"] == "STEX v0.2"
    assert profile["review_status"] == "proposed"
    assert profile["structural_exposure"] == 36.6353
    assert profile["augmentation_likelihood"] == 3.2538
    assert all(task["rubric_version"] == "STEX v0.2" for task in tasks)
    assert all(task["review_status"] == "proposed" for task in tasks)
    assert all(
        key not in task
        for task in tasks
        for key in ("reviewed_by", "reviewed_at_utc", "review_note")
    )


def test_laborers_v02_aggregate_matches_records_and_excludes_unrated_task():
    profile = json.loads(
        (ROOT / "data/stex/occupations/53-7062_00.stex.json").read_text()
    )
    tasks = load_occupation_stex_tasks(CODE)
    assert len(tasks) == 14
    assert sum(task["importance_status"] == "rated" for task in tasks) == 13
    damage_task = next(task for task in tasks if task["task_id"] == "1001441")
    assert damage_task["source_importance"] == 0.0
    assert damage_task["importance_status"] == "unrated"

    from gvai.postlabor.stex.review import _task_record_from_payload

    result = aggregate_occupation_stex(
        [_task_record_from_payload(task) for task in tasks]
    )
    assert result.to_dict()["structural_exposure"] == profile["structural_exposure"]
    assert result.to_dict()["augmentation_likelihood"] == profile["augmentation_likelihood"]
    assert result.to_dict()["total_importance_weight"] == 918.0


def test_laborers_v02_rationale_is_task_specific():
    tasks = load_occupation_stex_tasks(CODE)

    assert len({task["rationale"] for task in tasks}) == 14
    assert all(
        "Explicit STEX v0.1 audit" not in task["rationale"]
        for task in tasks
    )
    assert "sortation" in next(
        task["rationale"] for task in tasks if task["task_id"] == "10782"
    )


def test_laborers_v02_has_complete_final_rating_map_and_ten_scope_revisions():
    expected = {
        "10789": (2.0, 2.0, 2.0), "10779": (4.0, 1.0, 1.0),
        "10781": (1.0, 3.0, 2.0), "10788": (1.0, 2.0, 3.0),
        "10782": (2.0, 3.0, 2.0), "10778": (3.0, 3.0, 1.0),
        "10780": (4.0, 1.0, 0.0), "10790": (1.0, 2.0, 3.0),
        "10787": (1.0, 2.0, 2.0), "10786": (1.0, 2.0, 3.0),
        "10783": (1.0, 2.0, 3.0), "10792": (2.0, 3.0, 2.0),
        "10796": (2.0, 2.0, 3.0), "1001441": (3.0, 3.0, 2.0),
    }
    tasks = {task["task_id"]: task for task in load_occupation_stex_tasks(CODE)}

    assert {
        task_id: (
            tasks[task_id]["digital_capability"],
            tasks[task_id]["physical_execution"],
            tasks[task_id]["human_presence_requirement"],
        )
        for task_id in expected
    } == expected
    initial_v02 = {
        "10789": (2, 3, 1), "10779": (4, 1, 1), "10781": (1, 4, 1),
        "10788": (1, 3, 2), "10782": (2, 4, 1), "10778": (3, 3, 1),
        "10780": (4, 1, 0), "10790": (1, 3, 2), "10787": (1, 3, 2),
        "10786": (1, 3, 2), "10783": (1, 3, 2), "10792": (2, 3, 1),
        "10796": (2, 3, 2), "1001441": (3, 3, 2),
    }
    assert sum(expected[task_id] != initial_v02[task_id] for task_id in expected) == 10

    report = (ROOT / "docs/stex/LABORERS_V0_2_RERATING_REPORT.md").read_text()
    assert "Ten physical tasks revised for occupation-wide scope." in report


def test_v02_documentation_distinguishes_physical_execution_from_human_presence():
    rubric = (ROOT / "docs/stex/STEX_V0_2_RUBRIC.md").read_text()

    assert "physical automation system" in rubric
    assert "Occupation-wide scope rule" in rubric
    assert "representative occupational settings" in rubric
    assert "required human presence" in rubric
    assert "physical task does not automatically receive `R=4`" in rubric
    assert "automated cargo sorting" in rubric
    assert "bedside care" in rubric


def test_laborers_v02_review_package_exposes_rubric_and_tasks():
    response = api_service.app.test_client().get(
        "/api/stex/review/occupation?code=53-7062.00"
    )

    assert response.status_code == 200
    package = response.get_json()["package"]
    assert package["review_status"] == "proposed"
    assert package["rubric_version"] == "STEX v0.2"
    assert len(package["tasks"]) == 14
    assert {task["rubric_version"] for task in package["tasks"]} == {"STEX v0.2"}


def test_v01_approved_profiles_and_production_are_unchanged(monkeypatch):
    profiles = list_occupation_stex_profiles()
    assert {profile["occupation_code"] for profile in profiles} == {
        "15-1252.00",
        "37-2021.00",
    }
    by_code = {profile["occupation_code"]: profile for profile in profiles}
    assert by_code["15-1252.00"]["structural_exposure"] == 75.9444
    assert by_code["37-2021.00"]["structural_exposure"] == 35.6614

    def fail_network(*args, **kwargs):
        raise AssertionError("production request attempted network access")

    monkeypatch.setattr(bls_module.requests, "post", fail_network)
    monkeypatch.setattr(oews_module.requests, "get", fail_network)
    response = api_service.app.test_client().get(
        "/api/stex/regional?area=0034980&year=2025&limit=10"
    )
    payload = response.get_json()
    assert payload["stex_covered_employment"] == 8800.0
    assert payload["coverage_percentage"] == 0.8005
    assert payload["covered_occupation_stex"] == 71.1379
    assert payload["methodology"]["regional_automation_score"] is None


def test_proposed_preview_if_laborers_approved_is_nonproduction():
    report = (ROOT / "docs/stex/LABORERS_V0_2_RERATING_REPORT.md").read_text()

    assert "Current production covered employment: 8,800" in report
    assert "Laborers employment: 33,120" in report
    assert "Projected covered employment if Laborers alone were approved: 41,920" in report
    assert "BLS All Occupations denominator: 1,099,300" in report
    assert "Laborers incremental coverage: 3.0128 percentage points" in report
    assert "PROJECTED COVERAGE IF LABORERS ALONE WERE APPROVED: 3.8133%" in report
    assert "FIVE-PROFILE PROPOSED PREVIEW (NOT LABORERS-ONLY): 13.4722%" in report
    assert "PROJECTED COVERAGE IF APPROVED: 13.4722%" not in report


def test_laborers_v02_generation_is_offline_and_proposal_only():
    source = (ROOT / "scripts/build_laborers_stex_v02.py").read_text()

    assert "requests" not in source
    assert "OnetClient" not in source
    assert 'review_status="proposed"' in source
    assert "approve_occupation" not in source