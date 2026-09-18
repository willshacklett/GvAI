from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import gvai.api_service as api_service
import gvai.postlabor.worker_personal_comparison as personal_comparison
from gvai.postlabor.sources.onet import OnetEducationLevel, OnetJobZone
from gvai.postlabor.stex.store import InvalidSTEXOccupationCode
from gvai.postlabor.worker_personal_comparison import (
    synthesize_worker_personal_comparison,
)
from gvai.postlabor.worker_profile import validate_worker_profile


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CODE = "37-2021.00"
TARGET_CODE = "37-3012.00"


def _full_profile_payload():
    return {
        "profile_version": "v1",
        "current_occupation": {
            "occupation_code": SOURCE_CODE,
            "occupation_title": "Pest Control Workers",
        },
        "experience": {"years_in_current_occupation": 8, "total_years_work_experience": 12},
        "education": {"highest_level": "High school diploma or equivalent", "field_of_study": ""},
        "credentials": ["State pesticide applicator credential"],
        "skills": ["Customer service", "Route scheduling", "Pest identification"],
        "wage": {"minimum_annual": 50000},
        "mobility": {"radius_miles": 25, "willing_to_relocate": False, "remote_preference": "no_preference"},
        "preferences": {"notes": "Daytime schedule preferred."},
    }


def _full_profile():
    return validate_worker_profile(_full_profile_payload())


class _FakeOnetClient:
    def job_zone(self, occupation_code):
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
        return [
            OnetEducationLevel(2, "High school diploma or equivalent", 60.0),
            OnetEducationLevel(4, "Some college, no degree", 25.0),
        ]

    def skills(self, occupation_code):
        from gvai.postlabor.workers.occupation_data import OccupationSkill
        return [
            OccupationSkill("2.A.1.a", "Active Listening", 75.0, "Giving full attention."),
            OccupationSkill("2.A.1.b", "Critical Thinking", 82.0, "Using logic and reasoning."),
            OccupationSkill("2.A.1.c", "Monitoring", 60.0, "Monitoring performance."),
            OccupationSkill("2.A.1.d", "Speaking", 55.0, "Talking to convey information."),
            OccupationSkill("2.A.1.e", "Coordination", 50.0, "Adjusting actions."),
            OccupationSkill("2.A.1.f", "Time Management", 40.0, "Managing one's own time."),
        ]


class _UnavailableOnetClient:
    def job_zone(self, occupation_code):
        raise RuntimeError("O*NET job zone unavailable")

    def education(self, occupation_code):
        raise RuntimeError("O*NET education unavailable")

    def skills(self, occupation_code):
        raise RuntimeError("O*NET skills unavailable")


def _region_payload():
    return {
        "supported": True,
        "oews_area_code": "0034980",
        "state": "Tennessee",
        "county": "Davidson County",
    }


def _wage_signal(*, status="known", specificity="exact"):
    if status == "known":
        return {
            "id": "occupation_regional_wage",
            "status": "known",
            "median_hourly_wage": 21.32,
            "median_annual_wage": 44350.0,
            "year": 2025,
            "source": "BLS OEWS time-series machine-readable data",
            "occupation_title": "Pesticide Handlers, Sprayers, and Applicators, Vegetation",
            "oews_occupation_code": "37-3012",
            "match_specificity": specificity,
            "explanation": (
                "OEWS does not publish a median wage specific to this "
                "occupation. This wage is the broader published OEWS "
                "category, not this detailed occupation."
                if specificity == "broader_category"
                else "This is the occupation's regional OEWS median wage within this labor-market area."
            ),
        }
    return {
        "id": "occupation_regional_wage",
        "status": "unknown",
        "median_hourly_wage": None,
        "median_annual_wage": None,
        "year": None,
        "source": None,
        "occupation_title": None,
        "oews_occupation_code": None,
        "match_specificity": None,
        "explanation": "Regional OEWS median wage data has not been packaged for this area and year, so it is unknown.",
    }


def _patch(monkeypatch, *, onet=None, region=None, wage=None):
    monkeypatch.setattr(
        personal_comparison,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: region if region is not None else _region_payload(),
    )
    monkeypatch.setattr(
        personal_comparison,
        "_occupation_regional_wage_signal",
        lambda *args, **kwargs: wage if wage is not None else _wage_signal(),
    )
    return onet or _FakeOnetClient()


FORBIDDEN_FIELD_NAMES = {
    "score", "fit", "rank", "recommendation", "qualification",
    "match", "gap", "transferability", "retraining_burden",
    "geographic_opportunity", "confidence",
}


def _collect_field_names(value, names):
    if isinstance(value, dict):
        for key, item in value.items():
            names.add(key)
            _collect_field_names(item, names)
    elif isinstance(value, list):
        for item in value:
            _collect_field_names(item, names)


# --- Profile ---------------------------------------------------------


def test_valid_self_reported_profile_produces_comparisons(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(
        _full_profile(), TARGET_CODE, latitude=36.16, longitude=-86.78, onet_client=onet
    )
    assert result["supported"] is True
    assert result["claim_source"] == "self_reported_worker_profile"
    assert {c["comparison_id"] for c in result["comparisons"]} == {
        "wage", "mobility", "education", "credentials", "skills", "experience",
    }


def test_minimal_profile_reports_not_provided(monkeypatch):
    onet = _patch(monkeypatch)
    profile = validate_worker_profile({"profile_version": "v1"})
    result = synthesize_worker_personal_comparison(profile, TARGET_CODE, onet_client=onet)
    wage = next(c for c in result["comparisons"] if c["comparison_id"] == "wage")
    assert wage["worker_fact"]["status"] == "not_provided"
    assert wage["worker_fact"]["minimum_annual"] is None


def test_missing_optional_values_stay_none_not_zero(monkeypatch):
    onet = _patch(monkeypatch)
    profile = validate_worker_profile({"profile_version": "v1"})
    result = synthesize_worker_personal_comparison(profile, TARGET_CODE, onet_client=onet)
    experience = next(c for c in result["comparisons"] if c["comparison_id"] == "experience")
    assert experience["worker_fact"]["years_in_current_occupation"] is None
    assert experience["worker_fact"]["years_in_current_occupation"] != 0


# --- Occupation invariants --------------------------------------------


def test_source_occupation_preserved_and_target_distinct(monkeypatch):
    onet = _patch(monkeypatch)
    profile = _full_profile()
    result = synthesize_worker_personal_comparison(profile, TARGET_CODE, onet_client=onet)
    assert result["source_occupation"]["occupation_code"] == SOURCE_CODE
    assert result["target_occupation"]["occupation_code"] == TARGET_CODE
    assert profile["current_occupation"]["occupation_code"] == SOURCE_CODE


def test_target_investigation_cannot_overwrite_source(monkeypatch):
    onet = _patch(monkeypatch)
    profile = _full_profile()
    before = json.dumps(profile, sort_keys=True)
    synthesize_worker_personal_comparison(profile, TARGET_CODE, onet_client=onet)
    after = json.dumps(profile, sort_keys=True)
    assert before == after


def test_same_source_and_target_code_handled_gracefully(monkeypatch):
    onet = _patch(monkeypatch)
    profile = _full_profile()
    result = synthesize_worker_personal_comparison(profile, SOURCE_CODE, onet_client=onet)
    assert result["source_equals_target"] is True


def test_invalid_target_code_raises(monkeypatch):
    onet = _patch(monkeypatch)
    with pytest.raises(InvalidSTEXOccupationCode):
        synthesize_worker_personal_comparison(_full_profile(), "not-a-code", onet_client=onet)


# --- Wage --------------------------------------------------------------


def test_wage_worker_minimum_and_exact_regional_wage_known(monkeypatch):
    onet = _patch(monkeypatch, wage=_wage_signal(specificity="exact"))
    result = synthesize_worker_personal_comparison(
        _full_profile(), TARGET_CODE, latitude=36.16, longitude=-86.78, onet_client=onet
    )
    wage = next(c for c in result["comparisons"] if c["comparison_id"] == "wage")
    assert wage["worker_fact"]["minimum_annual"] == 50000
    assert wage["occupational_evidence"]["median_annual_wage"] == 44350.0
    assert wage["occupational_evidence"]["match_specificity"] == "exact"
    assert wage["status"] == "both_reported"


def test_wage_broader_category_caveat_preserved(monkeypatch):
    onet = _patch(monkeypatch, wage=_wage_signal(specificity="broader_category"))
    result = synthesize_worker_personal_comparison(
        _full_profile(), TARGET_CODE, latitude=36.16, longitude=-86.78, onet_client=onet
    )
    wage = next(c for c in result["comparisons"] if c["comparison_id"] == "wage")
    assert "broader" in wage["limitation"].lower()


def test_wage_regional_wage_unknown(monkeypatch):
    onet = _patch(monkeypatch, wage=_wage_signal(status="unknown"))
    result = synthesize_worker_personal_comparison(
        _full_profile(), TARGET_CODE, latitude=36.16, longitude=-86.78, onet_client=onet
    )
    wage = next(c for c in result["comparisons"] if c["comparison_id"] == "wage")
    assert wage["occupational_evidence"]["status"] == "unknown"
    assert wage["occupational_evidence"]["median_annual_wage"] is None


def test_wage_worker_wage_missing(monkeypatch):
    onet = _patch(monkeypatch)
    profile = validate_worker_profile({"profile_version": "v1"})
    result = synthesize_worker_personal_comparison(profile, TARGET_CODE, onet_client=onet)
    wage = next(c for c in result["comparisons"] if c["comparison_id"] == "wage")
    assert wage["worker_fact"]["status"] == "not_provided"


# --- Education / preparation --------------------------------------------


def test_education_worker_and_job_zone_known(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    education = next(c for c in result["comparisons"] if c["comparison_id"] == "education")
    assert education["worker_fact"]["highest_level"] == "High school diploma or equivalent"
    assert education["occupational_evidence"]["job_zone"]["status"] == "known"
    assert education["occupational_evidence"]["job_zone"]["job_zone_code"] == 3


def test_education_survey_known(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    education = next(c for c in result["comparisons"] if c["comparison_id"] == "education")
    levels = education["occupational_evidence"]["education_survey"]["levels"]
    assert any(level["title"] == "High school diploma or equivalent" for level in levels)


def test_occupational_preparation_unavailable(monkeypatch):
    onet = _patch(monkeypatch, onet=_UnavailableOnetClient())
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    education = next(c for c in result["comparisons"] if c["comparison_id"] == "education")
    assert education["occupational_evidence"]["job_zone"]["status"] == "unavailable"
    assert education["occupational_evidence"]["education_survey"]["status"] == "unavailable"


def test_education_comparison_makes_no_qualification_claim(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    education = next(c for c in result["comparisons"] if c["comparison_id"] == "education")
    assert "not proof of qualification" in education["limitation"].lower()


# --- Credentials ---------------------------------------------------------


def test_credentials_self_reported_are_shown(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    credentials = next(c for c in result["comparisons"] if c["comparison_id"] == "credentials")
    assert credentials["worker_fact"]["items"] == ["State pesticide applicator credential"]


def test_credentials_no_verification_claim(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    credentials = next(c for c in result["comparisons"] if c["comparison_id"] == "credentials")
    text = credentials["occupational_evidence"]["explanation"] + credentials["limitation"]
    assert "does not" in text.lower() or "cannot" in text.lower()


def test_credentials_no_invented_target_requirement(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    credentials = next(c for c in result["comparisons"] if c["comparison_id"] == "credentials")
    assert credentials["occupational_evidence"]["status"] == "unavailable"


# --- Skills ---------------------------------------------------------------


def test_skills_shown_as_separate_lists(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    skills = next(c for c in result["comparisons"] if c["comparison_id"] == "skills")
    assert skills["worker_fact"]["items"] == [
        "Customer service", "Route scheduling", "Pest identification",
    ]
    target_names = [item["name"] for item in skills["occupational_evidence"]["items"]]
    assert target_names == ["Critical Thinking", "Active Listening", "Monitoring", "Speaking", "Coordination"]


def test_skills_no_matching_or_gap_inference(monkeypatch):
    # Contract check: no matched/gap/similarity *fields* -- legitimate
    # explanatory prose disclaiming matching is expected and allowed.
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    skills = next(c for c in result["comparisons"] if c["comparison_id"] == "skills")
    names = set()
    _collect_field_names(skills, names)
    assert not (names & {"matched_skills", "missing_skills", "skill_gaps", "similarity_score"})


def _flatten_str(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _flatten_str(item)
    elif isinstance(value, list):
        for item in value:
            yield from _flatten_str(item)


def test_skills_no_similarity_score_field(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    skills = next(c for c in result["comparisons"] if c["comparison_id"] == "skills")
    names = set()
    _collect_field_names(skills, names)
    assert not (names & FORBIDDEN_FIELD_NAMES)


# --- Experience ------------------------------------------------------------


def test_experience_years_preserved(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    experience = next(c for c in result["comparisons"] if c["comparison_id"] == "experience")
    assert experience["worker_fact"]["years_in_current_occupation"] == 8
    assert experience["worker_fact"]["total_years_work_experience"] == 12


def test_experience_related_experience_text_independent(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    experience = next(c for c in result["comparisons"] if c["comparison_id"] == "experience")
    assert experience["occupational_evidence"]["related_experience"] == (
        "Several months to one year of experience."
    )


def test_experience_no_qualification_inference(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(_full_profile(), TARGET_CODE, onet_client=onet)
    experience = next(c for c in result["comparisons"] if c["comparison_id"] == "experience")
    assert "does not convert" in experience["limitation"].lower()


# --- Missingness -------------------------------------------------------


def test_missing_stays_unavailable_not_zero_or_fifty(monkeypatch):
    onet = _patch(monkeypatch, onet=_UnavailableOnetClient(), wage=_wage_signal(status="unknown"))
    profile = validate_worker_profile({"profile_version": "v1"})
    result = synthesize_worker_personal_comparison(profile, TARGET_CODE, onet_client=onet)
    for comparison in result["comparisons"]:
        for value in _flatten_str(comparison):
            assert value not in ("0", "50", "50.0")


def test_no_numeric_zero_or_fifty_fallback_values(monkeypatch):
    onet = _patch(monkeypatch, onet=_UnavailableOnetClient(), wage=_wage_signal(status="unknown"))
    profile = validate_worker_profile({"profile_version": "v1"})
    result = synthesize_worker_personal_comparison(profile, TARGET_CODE, onet_client=onet)
    wage = next(c for c in result["comparisons"] if c["comparison_id"] == "wage")
    assert wage["worker_fact"]["minimum_annual"] is None
    assert wage["occupational_evidence"]["median_annual_wage"] is None


# --- Methodology: no forbidden fields anywhere in the payload -----------


def test_no_forbidden_scoring_fields_anywhere(monkeypatch):
    onet = _patch(monkeypatch)
    result = synthesize_worker_personal_comparison(
        _full_profile(), TARGET_CODE, latitude=36.16, longitude=-86.78, onet_client=onet
    )
    names = set()
    _collect_field_names(result, names)
    assert not (names & FORBIDDEN_FIELD_NAMES)


def test_explanatory_prose_about_no_qualification_does_not_fail_naive_scan():
    # Sanity check: legitimate disclaimers use these words in prose, not as
    # field names. This test documents that only *field names* are banned.
    text = "GVAI does not determine qualification."
    assert "qualification" in text.lower()


# --- Privacy -------------------------------------------------------------


def test_api_requires_post_body_not_query_params():
    with api_service.app.test_client() as client:
        response = client.post(
            "/api/worker/personal-comparison",
            data=json.dumps({
                "profile": _full_profile_payload(),
                "target_occupation_code": TARGET_CODE,
            }),
            content_type="application/json",
        )
    assert response.status_code in (200, 400, 500)
    # No GET endpoint is registered for this route.
    assert not any(
        rule.rule == "/api/worker/personal-comparison" and "GET" in rule.methods
        for rule in api_service.app.url_map.iter_rules()
    )


def test_api_does_not_echo_profile_values_on_error(monkeypatch):
    with api_service.app.test_client() as client:
        response = client.post(
            "/api/worker/personal-comparison",
            data=json.dumps({
                "profile": {"profile_version": "v1", "skills": ["x" * 200]},
                "target_occupation_code": TARGET_CODE,
            }),
            content_type="application/json",
        )
    body = response.get_data(as_text=True)
    assert "x" * 200 not in body


def test_api_profile_not_persisted(monkeypatch, tmp_path):
    onet = _patch(monkeypatch)
    monkeypatch.setattr(
        "gvai.postlabor.worker_personal_comparison.OnetClient",
        lambda *args, **kwargs: onet,
    )
    with api_service.app.test_client() as client:
        client.post(
            "/api/worker/personal-comparison",
            data=json.dumps({
                "profile": _full_profile_payload(),
                "target_occupation_code": TARGET_CODE,
            }),
            content_type="application/json",
        )
    # No file-based or in-memory persistence path exists in this module.
    import gvai.postlabor.worker_personal_comparison as module
    assert not hasattr(module, "_STORE")
    assert not hasattr(module, "_PROFILE_CACHE")


def test_lat_lon_required_together():
    with api_service.app.test_client() as client:
        response = client.post(
            "/api/worker/personal-comparison",
            data=json.dumps({
                "profile": _full_profile_payload(),
                "target_occupation_code": TARGET_CODE,
                "lat": 36.16,
            }),
            content_type="application/json",
        )
    assert response.status_code == 400


def test_only_occupation_and_region_identifiers_sent_to_onet(monkeypatch):
    seen_args = []

    class _RecordingOnetClient:
        def job_zone(self, occupation_code):
            seen_args.append(occupation_code)
            return OnetJobZone(3, "Job Zone 3", "edu", "exp", "training", "examples", "svp")

        def education(self, occupation_code):
            seen_args.append(occupation_code)
            return []

        def skills(self, occupation_code):
            seen_args.append(occupation_code)
            return []

    monkeypatch.setattr(
        personal_comparison,
        "synthesize_region_labor_intelligence",
        lambda *args, **kwargs: _region_payload(),
    )
    monkeypatch.setattr(
        personal_comparison,
        "_occupation_regional_wage_signal",
        lambda *args, **kwargs: _wage_signal(),
    )
    synthesize_worker_personal_comparison(
        _full_profile(), TARGET_CODE, onet_client=_RecordingOnetClient()
    )
    for value in seen_args:
        assert value == TARGET_CODE
        assert "pesticide" not in value.lower()
        assert "50000" not in value
