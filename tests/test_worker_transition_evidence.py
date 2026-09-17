from __future__ import annotations

import json

import gvai.api_service as api_service
import gvai.postlabor.worker_transition_evidence as worker_transition_evidence
from gvai.postlabor.sources.onet import OnetAbility, OnetKnowledge, OnetWorkActivity
from gvai.postlabor.workers.occupation_data import OccupationSkill
from gvai.postlabor.worker_transition_evidence import (
    EMPHASIS_MORE_IN_SOURCE,
    EMPHASIS_MORE_IN_TARGET,
    EMPHASIS_SIMILAR,
    InvalidSTEXOccupationCode,
    TRANSITION_EVIDENCE_MATERIALITY_THRESHOLD,
    synthesize_worker_transition_evidence,
)


SOURCE_CODE = "37-2021.00"
TARGET_CODE = "37-3012.00"


class _FakeOnetClient:
    """Simulates the shared 35-skill / 41-work-activity O*NET taxonomy."""

    def skills(self, occupation_code):
        if occupation_code == SOURCE_CODE:
            return [
                OccupationSkill("2.A.1.a", "Reading Comprehension", 47.0, "desc a"),
                OccupationSkill("2.A.1.b", "Active Listening", 50.0, "desc b"),
                OccupationSkill("2.B.1.a", "Equipment Selection", 60.0, "desc c"),
            ]
        return [
            OccupationSkill("2.A.1.a", "Reading Comprehension", 45.0, "desc a"),
            OccupationSkill("2.A.1.b", "Active Listening", 66.0, "desc b"),
            OccupationSkill("2.B.1.a", "Equipment Selection", 40.0, "desc c"),
        ]

    def work_activities(self, occupation_code):
        if occupation_code == SOURCE_CODE:
            return [
                OnetWorkActivity("4.A.1.a.1", "Getting Information", "desc x", 55.0),
                OnetWorkActivity("4.A.3.b.2", "Handling Objects", "desc y", 70.0),
            ]
        return [
            OnetWorkActivity("4.A.1.a.1", "Getting Information", "desc x", 53.0),
            OnetWorkActivity("4.A.3.b.2", "Handling Objects", "desc y", 90.0),
        ]

    def knowledge(self, occupation_code):
        if occupation_code == SOURCE_CODE:
            return [
                OnetKnowledge("2.C.1.a", "Biology", "desc k1", 40.0),
                OnetKnowledge("2.C.9.a", "Public Safety and Security", "desc k2", 65.0),
            ]
        return [
            OnetKnowledge("2.C.1.a", "Biology", "desc k1", 62.0),
            OnetKnowledge("2.C.9.a", "Public Safety and Security", "desc k2", 63.0),
        ]

    def abilities(self, occupation_code):
        if occupation_code == SOURCE_CODE:
            return [
                OnetAbility("1.A.1.a.1", "Oral Comprehension", "desc a1", 58.0),
                OnetAbility("1.A.4.a.1", "Near Vision", "desc a2", 75.0),
            ]
        return [
            OnetAbility("1.A.1.a.1", "Oral Comprehension", "desc a1", 55.0),
            OnetAbility("1.A.4.a.1", "Near Vision", "desc a2", 45.0),
        ]


class _ZeroAndMissingImportanceOnetClient:
    """Distinguishes a real O*NET importance of 0 from a missing value."""

    def skills(self, occupation_code):
        return [
            OccupationSkill("2.A.1.a", "Real Zero Skill", 0.0, "desc z"),
            OccupationSkill("2.A.1.b", "Missing Skill", None, "desc m"),
        ]

    def work_activities(self, occupation_code):
        return [
            OnetWorkActivity("4.A.1.a.1", "Real Zero Activity", "desc z", 0.0),
            OnetWorkActivity("4.A.1.a.2", "Missing Activity", "desc m", None),
        ]

    def knowledge(self, occupation_code):
        if occupation_code == SOURCE_CODE:
            return [
                OnetKnowledge("2.C.1.a", "Real Zero Knowledge", "desc z", 0.0),
                OnetKnowledge("2.C.9.a", "Missing Knowledge", "desc m", None),
            ]
        return [
            OnetKnowledge("2.C.1.a", "Real Zero Knowledge", "desc z", 0.0),
            OnetKnowledge("2.C.9.a", "Missing Knowledge", "desc m", None),
        ]

    def abilities(self, occupation_code):
        if occupation_code == SOURCE_CODE:
            return [
                OnetAbility("1.A.1.a.1", "Real Zero Ability", "desc z", 0.0),
                OnetAbility("1.A.4.a.1", "Missing Ability", "desc m", None),
            ]
        return [
            OnetAbility("1.A.1.a.1", "Real Zero Ability", "desc z", 0.0),
            OnetAbility("1.A.4.a.1", "Missing Ability", "desc m", None),
        ]


class _UnavailableOnetClient:
    def skills(self, occupation_code):
        raise RuntimeError("O*NET skills unavailable")

    def work_activities(self, occupation_code):
        raise RuntimeError("O*NET work activities unavailable")

    def knowledge(self, occupation_code):
        raise RuntimeError("O*NET knowledge unavailable")

    def abilities(self, occupation_code):
        raise RuntimeError("O*NET abilities unavailable")


class _PartiallyUnavailableOnetClient:
    """Skills succeed but work activities fail."""

    def skills(self, occupation_code):
        return [
            OccupationSkill("2.A.1.a", "Reading Comprehension", 47.0, "desc a"),
        ]

    def work_activities(self, occupation_code):
        raise RuntimeError("O*NET work activities unavailable")

    def knowledge(self, occupation_code):
        raise RuntimeError("O*NET knowledge unavailable")

    def abilities(self, occupation_code):
        raise RuntimeError("O*NET abilities unavailable")


def test_factual_comparison_preserves_source_and_target_importance():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    items = result["skill_comparison"]["items"]
    by_id = {item["id"]: item for item in items}

    assert by_id["2.A.1.a"]["source_importance"] == 47.0
    assert by_id["2.A.1.a"]["target_importance"] == 45.0
    assert by_id["2.A.1.b"]["source_importance"] == 50.0
    assert by_id["2.A.1.b"]["target_importance"] == 66.0


def test_deterministic_difference_calculation_is_signed_target_minus_source():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    items = result["work_activity_comparison"]["items"]
    by_id = {item["id"]: item for item in items}

    # target(53.0) - source(55.0) = -2.0
    assert by_id["4.A.1.a.1"]["importance_difference"] == -2.0
    # target(90.0) - source(70.0) = 20.0
    assert by_id["4.A.3.b.2"]["importance_difference"] == 20.0


def test_presentation_grouping_uses_documented_threshold():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    activities = {
        item["id"]: item for item in result["work_activity_comparison"]["items"]
    }
    skills = {item["id"]: item for item in result["skill_comparison"]["items"]}

    # -2.0 is within the threshold -> similar emphasis.
    assert activities["4.A.1.a.1"]["emphasis"] == EMPHASIS_SIMILAR
    # +20.0 exceeds the threshold -> more emphasized in target.
    assert activities["4.A.3.b.2"]["emphasis"] == EMPHASIS_MORE_IN_TARGET
    # -2.0 for Reading Comprehension is within the threshold -> similar.
    assert skills["2.A.1.a"]["emphasis"] == EMPHASIS_SIMILAR
    # +16.0 for Active Listening exceeds the threshold -> more in target.
    assert skills["2.A.1.b"]["emphasis"] == EMPHASIS_MORE_IN_TARGET
    # -20.0 for Equipment Selection exceeds the threshold -> more in source.
    assert skills["2.B.1.a"]["emphasis"] == EMPHASIS_MORE_IN_SOURCE

    assert result["materiality_threshold"] == TRANSITION_EVIDENCE_MATERIALITY_THRESHOLD


def test_unavailable_onet_behavior_returns_explicit_unavailable_status():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_UnavailableOnetClient(),
    )

    assert result["work_activity_comparison"]["status"] == "unavailable"
    assert result["work_activity_comparison"]["items"] == []
    assert result["work_activity_comparison"]["explanation"]

    assert result["skill_comparison"]["status"] == "unavailable"
    assert result["skill_comparison"]["items"] == []
    assert result["skill_comparison"]["explanation"]

    assert result["work_activity_comparison"]["explanation"] in result["constraints"]
    assert result["skill_comparison"]["explanation"] in result["constraints"]


def test_partial_unavailability_does_not_affect_other_signal():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_PartiallyUnavailableOnetClient(),
    )

    assert result["work_activity_comparison"]["status"] == "unavailable"
    assert result["skill_comparison"]["status"] == "known"


def test_no_zero_or_fifty_fallback_for_unavailable_data():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_UnavailableOnetClient(),
    )

    serialized = json.dumps(result)
    assert '"importance_difference": 0' not in serialized
    assert '"source_importance": 50.0' not in serialized
    assert '"target_importance": 50.0' not in serialized
    assert result["work_activity_comparison"]["items"] == []
    assert result["skill_comparison"]["items"] == []


def test_no_similarity_qualification_or_retraining_score_in_response():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    serialized = json.dumps(result).lower()
    prohibited = (
        "similarity",
        "transferability",
        "qualification_score",
        "retraining_burden",
        "recommendation",
        "composite",
        "gvai_score",
        "strength",
        "weakness",
        "gap",
        "deficiency",
    )
    assert not any(field in serialized for field in prohibited)


def test_deterministic_ordering_across_repeated_calls():
    first = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )
    second = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    first_order = [item["id"] for item in first["skill_comparison"]["items"]]
    second_order = [item["id"] for item in second["skill_comparison"]["items"]]
    assert first_order == second_order

    # Ordered by descending absolute importance difference.
    diffs = [
        abs(item["importance_difference"])
        for item in first["skill_comparison"]["items"]
    ]
    assert diffs == sorted(diffs, reverse=True)


def test_invalid_occupation_code_raises():
    try:
        synthesize_worker_transition_evidence(
            "not-a-code",
            TARGET_CODE,
            onet_client=_FakeOnetClient(),
        )
        assert False, "Expected InvalidSTEXOccupationCode"
    except InvalidSTEXOccupationCode:
        pass


def test_titles_default_to_codes_when_not_supplied():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )
    assert result["source_occupation_title"] == SOURCE_CODE
    assert result["target_occupation_title"] == TARGET_CODE


def test_titles_are_preserved_when_supplied():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
        source_occupation_title="Pest Control Workers",
        target_occupation_title=(
            "Pesticide Handlers, Sprayers, and Applicators, Vegetation"
        ),
    )
    assert result["source_occupation_title"] == "Pest Control Workers"
    assert result["target_occupation_title"] == (
        "Pesticide Handlers, Sprayers, and Applicators, Vegetation"
    )


def test_explanation_distinguishes_occupational_evidence_from_personal_qualification():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )
    explanation = result["explanation"].lower()
    assert "does not determine whether an individual is qualified" in explanation
    assert "personally possesses or lacks a skill" in explanation


def test_knowledge_comparison_preserves_source_and_target_importance():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    items = result["knowledge_comparison"]["items"]
    by_id = {item["id"]: item for item in items}

    assert by_id["2.C.1.a"]["source_importance"] == 40.0
    assert by_id["2.C.1.a"]["target_importance"] == 62.0
    assert by_id["2.C.1.a"]["importance_difference"] == 22.0
    assert by_id["2.C.1.a"]["emphasis"] == EMPHASIS_MORE_IN_TARGET

    # target(63.0) - source(65.0) = -2.0, within threshold -> similar.
    assert by_id["2.C.9.a"]["importance_difference"] == -2.0
    assert by_id["2.C.9.a"]["emphasis"] == EMPHASIS_SIMILAR


def test_ability_comparison_preserves_source_and_target_importance():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    items = result["ability_comparison"]["items"]
    by_id = {item["id"]: item for item in items}

    # target(45.0) - source(75.0) = -30.0
    assert by_id["1.A.4.a.1"]["source_importance"] == 75.0
    assert by_id["1.A.4.a.1"]["target_importance"] == 45.0
    assert by_id["1.A.4.a.1"]["importance_difference"] == -30.0
    assert by_id["1.A.4.a.1"]["emphasis"] == EMPHASIS_MORE_IN_SOURCE


def test_knowledge_and_ability_comparison_unavailable_status():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_UnavailableOnetClient(),
    )

    assert result["knowledge_comparison"]["status"] == "unavailable"
    assert result["knowledge_comparison"]["items"] == []
    assert result["knowledge_comparison"]["explanation"] in result["constraints"]

    assert result["ability_comparison"]["status"] == "unavailable"
    assert result["ability_comparison"]["items"] == []
    assert result["ability_comparison"]["explanation"] in result["constraints"]


def test_real_zero_importance_is_kept_but_missing_importance_is_excluded():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_ZeroAndMissingImportanceOnetClient(),
    )

    knowledge_ids = {
        item["id"] for item in result["knowledge_comparison"]["items"]
    }
    ability_ids = {
        item["id"] for item in result["ability_comparison"]["items"]
    }
    skill_ids = {
        item["id"] for item in result["skill_comparison"]["items"]
    }
    activity_ids = {
        item["id"] for item in result["work_activity_comparison"]["items"]
    }

    # A real O*NET importance of 0 on both sides is a comparable fact.
    assert "2.C.1.a" in knowledge_ids
    assert "1.A.1.a.1" in ability_ids
    assert "2.A.1.a" in skill_ids
    assert "4.A.1.a.1" in activity_ids

    # A missing importance value must never be silently treated as 0.
    assert "2.C.9.a" not in knowledge_ids
    assert "1.A.4.a.1" not in ability_ids
    assert "2.A.1.b" not in skill_ids
    assert "4.A.1.a.2" not in activity_ids

    knowledge_by_id = {
        item["id"]: item for item in result["knowledge_comparison"]["items"]
    }
    assert knowledge_by_id["2.C.1.a"]["source_importance"] == 0.0
    assert knowledge_by_id["2.C.1.a"]["target_importance"] == 0.0
    assert knowledge_by_id["2.C.1.a"]["importance_difference"] == 0.0

    skill_by_id = {
        item["id"]: item for item in result["skill_comparison"]["items"]
    }
    assert skill_by_id["2.A.1.a"]["source_importance"] == 0.0
    assert skill_by_id["2.A.1.a"]["target_importance"] == 0.0

    activity_by_id = {
        item["id"]: item
        for item in result["work_activity_comparison"]["items"]
    }
    assert activity_by_id["4.A.1.a.1"]["source_importance"] == 0.0
    assert activity_by_id["4.A.1.a.1"]["target_importance"] == 0.0


def test_no_prohibited_vocabulary_in_knowledge_or_ability_comparison():
    result = synthesize_worker_transition_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    serialized = json.dumps(result).lower()
    prohibited = (
        "similarity",
        "qualification_score",
        "retraining_burden",
        "composite",
        "strength",
        "weakness",
        "gap",
        "deficiency",
    )
    assert not any(field in serialized for field in prohibited)


# --- API endpoint tests -----------------------------------------------


def test_api_transition_evidence_requires_source_and_target():
    client = api_service.app.test_client()
    response = client.get("/api/worker/transition-evidence?source=37-2021.00")

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_transition_evidence_rejects_invalid_code():
    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/transition-evidence?source=not-a-code&target=37-3012.00"
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_transition_evidence_success(monkeypatch):
    monkeypatch.setattr(
        worker_transition_evidence,
        "OnetClient",
        _FakeOnetClient,
    )

    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/transition-evidence"
        f"?source={SOURCE_CODE}&target={TARGET_CODE}"
        "&source_title=Pest%20Control%20Workers"
        "&target_title=Pesticide%20Handlers"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["source_occupation_code"] == SOURCE_CODE
    assert data["target_occupation_code"] == TARGET_CODE
    assert data["source_occupation_title"] == "Pest Control Workers"
    assert data["target_occupation_title"] == "Pesticide Handlers"
    assert data["work_activity_comparison"]["status"] == "known"
    assert data["skill_comparison"]["status"] == "known"


def test_api_transition_evidence_unavailable(monkeypatch):
    monkeypatch.setattr(
        worker_transition_evidence,
        "OnetClient",
        _UnavailableOnetClient,
    )

    client = api_service.app.test_client()
    response = client.get(
        f"/api/worker/transition-evidence?source={SOURCE_CODE}&target={TARGET_CODE}"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["work_activity_comparison"]["status"] == "unavailable"
    assert data["work_activity_comparison"]["items"] == []
    assert data["skill_comparison"]["status"] == "unavailable"
    assert data["skill_comparison"]["items"] == []
