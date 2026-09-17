from __future__ import annotations

import json

import gvai.api_service as api_service
import gvai.postlabor.worker_transition_preparation as worker_transition_preparation
from gvai.postlabor.sources.onet import OnetEducationLevel, OnetJobZone
from gvai.postlabor.worker_transition_preparation import (
    InvalidSTEXOccupationCode,
    synthesize_worker_transition_preparation_evidence,
)


SOURCE_CODE = "37-2021.00"
TARGET_CODE = "37-3012.00"


class _FakeOnetClient:
    def job_zone(self, occupation_code):
        if occupation_code == SOURCE_CODE:
            return OnetJobZone(
                code=2,
                title="Job Zone 1-2: Very Little to Some Preparation Needed",
                education="Usually requires a high school diploma or GED.",
                related_experience="Little or no previous experience.",
                job_training="A few days to a few months of training.",
                job_zone_examples="Pest control workers, groundskeepers.",
                svp_range="(Below 6.0)",
            )
        return OnetJobZone(
            code=3,
            title="Job Zone 3: Medium Preparation Needed",
            education="Usually requires vocational training or an associate's degree.",
            related_experience="Several months to one year of experience.",
            job_training="Ranges from six months to a year.",
            job_zone_examples="Pesticide handlers, sprayers, and applicators.",
            svp_range="(6.0 to < 7.0)",
        )

    def education(self, occupation_code):
        if occupation_code == SOURCE_CODE:
            return [
                OnetEducationLevel(2, "High school diploma or equivalent", 85.0),
                OnetEducationLevel(3, "Post-secondary certificate", 14.0),
            ]
        return [
            OnetEducationLevel(2, "High school diploma or equivalent", 60.0),
            OnetEducationLevel(4, "Some college, no degree", 25.0),
        ]


class _UnavailableOnetClient:
    def job_zone(self, occupation_code):
        raise RuntimeError("O*NET job zone unavailable")

    def education(self, occupation_code):
        raise RuntimeError("O*NET education unavailable")


class _ZeroAndMissingOnetClient:
    """Distinguishes real O*NET 0%/'' values from missing/null values."""

    def job_zone(self, occupation_code):
        return OnetJobZone(
            code=2,
            title="Job Zone 1-2",
            education=None,
            related_experience="",
            job_training=None,
            job_zone_examples=None,
            svp_range=None,
        )

    def education(self, occupation_code):
        return [
            OnetEducationLevel(2, "High school diploma or equivalent", 0.0),
            OnetEducationLevel(3, "Post-secondary certificate", None),
        ]


def test_source_and_target_job_zone_are_reported_independently():
    result = synthesize_worker_transition_preparation_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    source_job_zone = result["source_preparation"]["job_zone"]
    target_job_zone = result["target_preparation"]["job_zone"]

    assert source_job_zone["status"] == "known"
    assert source_job_zone["job_zone_code"] == 2
    assert target_job_zone["status"] == "known"
    assert target_job_zone["job_zone_code"] == 3
    assert source_job_zone["education"] != target_job_zone["education"]


def test_source_occupation_job_zone_values_are_unmodified():
    result = synthesize_worker_transition_preparation_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    source_job_zone = result["source_preparation"]["job_zone"]
    assert source_job_zone["svp_range"] == "(Below 6.0)"
    assert (
        source_job_zone["related_experience"]
        == "Little or no previous experience."
    )


def test_education_distribution_preserved_per_occupation():
    result = synthesize_worker_transition_preparation_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )

    source_levels = {
        level["title"]: level["percentage_of_respondents"]
        for level in result["source_preparation"]["education"]["levels"]
    }
    target_levels = {
        level["title"]: level["percentage_of_respondents"]
        for level in result["target_preparation"]["education"]["levels"]
    }

    assert source_levels["High school diploma or equivalent"] == 85.0
    assert target_levels["High school diploma or equivalent"] == 60.0
    assert target_levels["Some college, no degree"] == 25.0


def test_unavailable_onet_data_stays_unavailable_not_zero_or_fifty():
    result = synthesize_worker_transition_preparation_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_UnavailableOnetClient(),
    )

    for evidence in (
        result["source_preparation"],
        result["target_preparation"],
    ):
        assert evidence["job_zone"]["status"] == "unavailable"
        assert evidence["job_zone"]["job_zone_code"] is None
        assert evidence["education"]["status"] == "unavailable"
        assert evidence["education"]["levels"] == []

    serialized = json.dumps(result)
    assert '"job_zone_code": 0' not in serialized
    assert '"percentage_of_respondents": 50' not in serialized
    assert len(result["constraints"]) == 4


def test_real_zero_and_empty_string_values_are_distinguished_from_missing():
    result = synthesize_worker_transition_preparation_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_ZeroAndMissingOnetClient(),
    )

    job_zone = result["source_preparation"]["job_zone"]
    # The request succeeded, so the job zone signal is known overall...
    assert job_zone["status"] == "known"
    # ...but a null upstream field stays None, never becomes "".
    assert job_zone["education"] is None
    assert job_zone["job_training"] is None
    # A real upstream "" is preserved as "", not conflated with missing.
    assert job_zone["related_experience"] == ""

    education_levels = {
        level["title"]: level["percentage_of_respondents"]
        for level in result["source_preparation"]["education"]["levels"]
    }
    # A real O*NET 0% is a fact and must be kept.
    assert education_levels["High school diploma or equivalent"] == 0.0
    # A missing percentage must never become 0 or 50.
    assert education_levels["Post-secondary certificate"] is None


def test_invalid_occupation_code_raises():
    try:
        synthesize_worker_transition_preparation_evidence(
            "not-a-code",
            TARGET_CODE,
            onet_client=_FakeOnetClient(),
        )
        assert False, "Expected InvalidSTEXOccupationCode"
    except InvalidSTEXOccupationCode:
        pass


def test_titles_default_to_codes_when_not_supplied():
    result = synthesize_worker_transition_preparation_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )
    assert result["source_occupation_title"] == SOURCE_CODE
    assert result["target_occupation_title"] == TARGET_CODE


def test_no_prohibited_scoring_vocabulary_in_response():
    result = synthesize_worker_transition_preparation_evidence(
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
        "gvai_score",
        "readiness_score",
        "preparation_gap",
    )
    assert not any(field in serialized for field in prohibited)
    assert "not a measure of how easy or hard" in serialized


def test_explanation_distinguishes_occupation_evidence_from_personal_qualification():
    result = synthesize_worker_transition_preparation_evidence(
        SOURCE_CODE,
        TARGET_CODE,
        onet_client=_FakeOnetClient(),
    )
    explanation = result["explanation"].lower()
    assert "does not state whether any individual worker" in explanation


# --- API endpoint tests -----------------------------------------------


def test_api_transition_preparation_requires_source_and_target():
    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/transition-preparation?source=37-2021.00"
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_transition_preparation_rejects_invalid_code():
    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/transition-preparation"
        "?source=not-a-code&target=37-3012.00"
    )

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_api_transition_preparation_success(monkeypatch):
    monkeypatch.setattr(
        worker_transition_preparation,
        "OnetClient",
        _FakeOnetClient,
    )

    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/transition-preparation"
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
    assert data["source_preparation"]["job_zone"]["status"] == "known"
    assert data["target_preparation"]["job_zone"]["status"] == "known"


def test_api_transition_preparation_unavailable(monkeypatch):
    monkeypatch.setattr(
        worker_transition_preparation,
        "OnetClient",
        _UnavailableOnetClient,
    )

    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/transition-preparation"
        f"?source={SOURCE_CODE}&target={TARGET_CODE}"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["source_preparation"]["job_zone"]["status"] == "unavailable"
    assert data["target_preparation"]["education"]["status"] == "unavailable"
