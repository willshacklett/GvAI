from __future__ import annotations

import json
from pathlib import Path

import gvai.api_service as api_service
import gvai.postlabor.worker_transition_action_plan as action_plan


SOURCE_CODE = "37-2021.00"
TARGET_CODE = "37-3012.00"
ROOT = Path(__file__).resolve().parents[1]


def _transition_evidence():
    comparison = {
        "status": "known",
        "items": [
            {
                "id": "example",
                "name": "Scheduling and Documenting Information",
                "emphasis": "more_emphasized_in_target",
            }
        ],
    }
    return {
        "source_occupation_title": "Pest Control Workers",
        "target_occupation_title": "Pesticide Handlers",
        "work_activity_comparison": comparison,
        "skill_comparison": comparison,
        "knowledge_comparison": comparison,
        "ability_comparison": comparison,
    }


def _preparation_evidence():
    return {
        "target_preparation": {
            "job_zone": {
                "status": "known",
                "title": "Job Zone 3: Medium Preparation Needed",
                "education": "Usually requires vocational training.",
                "related_experience": "Several months of experience.",
                "job_training": "Six months to a year.",
            },
            "education": {
                "status": "known",
                "levels": [{
                    "title": "High school diploma or equivalent",
                    "percentage_of_respondents": 60.0,
                }],
            },
        },
    }


def _region_outlook(*, specificity="exact", wage_status="known"):
    wage = {
        "status": wage_status,
        "explanation": "Regional wage is unavailable, not zero.",
    }
    if wage_status == "known":
        wage.update({
            "median_hourly_wage": 21.32,
            "median_annual_wage": 44350.0,
            "source_year": 2024,
            "match_specificity": specificity,
            "explanation": "Broader OEWS category wage." if specificity == "broader_category" else "Regional OEWS wage.",
        })
    return {
        "supported": True,
        "occupation": {
            "regional_wage": wage,
            "regional_employment": {
                "status": "known",
                "employment": 1250.0,
                "source_year": 2024,
                "match_specificity": specificity,
                "explanation": "Broader OEWS category employment." if specificity == "broader_category" else "Regional OEWS employment.",
            },
        },
    }


def _patch_evidence(monkeypatch, *, region=None, preparation=None, transition=None):
    monkeypatch.setattr(
        action_plan,
        "synthesize_worker_transition_evidence",
        lambda *args, **kwargs: transition or _transition_evidence(),
    )
    monkeypatch.setattr(
        action_plan,
        "synthesize_worker_transition_preparation_evidence",
        lambda *args, **kwargs: preparation or _preparation_evidence(),
    )
    monkeypatch.setattr(
        action_plan,
        "synthesize_worker_region_outlook",
        lambda *args, **kwargs: region or _region_outlook(),
    )


def test_action_plan_has_fixed_evidence_backed_order(monkeypatch):
    _patch_evidence(monkeypatch)

    first = action_plan.synthesize_worker_transition_action_plan(
        SOURCE_CODE, TARGET_CODE, latitude=36.16, longitude=-86.78
    )
    second = action_plan.synthesize_worker_transition_action_plan(
        SOURCE_CODE, TARGET_CODE, latitude=36.16, longitude=-86.78
    )

    expected = [
        "review_typical_preparation",
        "compare_local_pay",
        "check_local_employment_presence",
        "review_occupational_differences",
        "verify_licensing_or_credentials",
        "compare_personal_background_separately",
    ]
    assert [item["action_id"] for item in first["actions"]] == expected
    assert first == second
    assert first["source_occupation_code"] == SOURCE_CODE
    assert first["target_occupation_code"] == TARGET_CODE


def test_broader_oews_caveat_is_preserved(monkeypatch):
    _patch_evidence(monkeypatch, region=_region_outlook(specificity="broader_category"))

    result = action_plan.synthesize_worker_transition_action_plan(
        SOURCE_CODE, TARGET_CODE, latitude=36.16, longitude=-86.78
    )
    local_actions = result["actions"][1:3]

    assert all("Broader OEWS category" in item["limitation"] for item in local_actions)


def test_unknown_regional_wage_is_unavailable_not_zero(monkeypatch):
    _patch_evidence(monkeypatch, region=_region_outlook(wage_status="unknown"))

    result = action_plan.synthesize_worker_transition_action_plan(
        SOURCE_CODE, TARGET_CODE, latitude=36.16, longitude=-86.78
    )
    wage_action = result["actions"][1]

    assert wage_action["evidence_status"] == "unavailable"
    assert "not zero" in wage_action["explanation"]
    assert wage_action["supporting_facts"] == []


def test_missing_preparation_omits_preparation_action(monkeypatch):
    preparation = _preparation_evidence()
    preparation["target_preparation"] = {
        "job_zone": {"status": "unavailable"},
        "education": {"status": "unavailable", "levels": []},
    }
    _patch_evidence(monkeypatch, preparation=preparation)

    result = action_plan.synthesize_worker_transition_action_plan(SOURCE_CODE, TARGET_CODE)

    assert "review_typical_preparation" not in [item["action_id"] for item in result["actions"]]
    assert result["regional_evidence_included"] is False


def test_plan_has_no_score_recommendation_or_qualification_claim(monkeypatch):
    _patch_evidence(monkeypatch)

    result = action_plan.synthesize_worker_transition_action_plan(SOURCE_CODE, TARGET_CODE)
    serialized = json.dumps(result).lower()

    for prohibited in (
        "transition_score", "similarity_score", "knowledge_similarity",
        "retraining_burden", "geographic_opportunity", "confidence_score",
        '"score"', "you are qualified", "you are not qualified",
        "you should change careers", "good fit", "bad fit",
    ):
        assert prohibited not in serialized
    assert "personal qualification" in serialized
    assert "not a recommendation" in serialized


def test_licensing_action_does_not_invent_a_requirement(monkeypatch):
    _patch_evidence(monkeypatch)

    result = action_plan.synthesize_worker_transition_action_plan(SOURCE_CODE, TARGET_CODE)
    licensing = next(
        item for item in result["actions"]
        if item["action_id"] == "verify_licensing_or_credentials"
    )

    assert licensing["evidence_status"] == "unavailable"
    assert "does not currently provide authoritative" in licensing["limitation"]


def test_api_action_plan_requires_source_and_target():
    client = api_service.app.test_client()
    response = client.get("/api/worker/transition-action-plan?source=37-2021.00")

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_main_globe_action_plan_contract_and_clearing():
    html = (ROOT / "web/index.html").read_text()

    assert 'id="transition-action-plan-status"' in html
    assert 'id="transition-action-plan-content"' in html
    assert "Things to investigate next" in html
    assert "/api/worker/transition-action-plan?source=" in html
    assert "clearTransitionActionPlan" in html