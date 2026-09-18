import json
from pathlib import Path

import pytest

import gvai.api_service as api_service
from gvai.postlabor.worker_profile import (
    WorkerProfileValidationError,
    validate_worker_profile,
)


ROOT = Path(__file__).resolve().parents[1]


def _full_profile():
    return {
        "profile_version": "v1",
        "current_occupation": {"occupation_code": "37-2021.00", "occupation_title": "Pest Control Workers"},
        "experience": {"years_in_current_occupation": 8, "total_years_work_experience": 12},
        "education": {"highest_level": "High school diploma or equivalent", "field_of_study": ""},
        "credentials": ["State pesticide applicator credential"],
        "skills": ["Customer service", "Route scheduling", "Pest identification"],
        "wage": {"minimum_annual": 50000},
        "mobility": {"radius_miles": 25, "willing_to_relocate": False, "remote_preference": "no_preference"},
        "preferences": {"notes": "Daytime schedule preferred."},
    }


def test_worker_profile_minimal_and_missing_values_are_normalized():
    profile = validate_worker_profile({"profile_version": "v1"})
    assert profile["experience"]["years_in_current_occupation"] is None
    assert profile["wage"]["current_hourly"] is None
    assert profile["credentials"] == []
    assert profile["mobility"]["willing_to_relocate"] is None


def test_worker_profile_full_profile_preserves_self_reported_facts():
    profile = validate_worker_profile(_full_profile())
    assert profile["claim_source"] == "self_reported"
    assert profile["current_occupation"]["occupation_code"] == "37-2021.00"
    assert profile["wage"]["minimum_annual"] == 50000
    assert profile["mobility"]["willing_to_relocate"] is False
    assert profile["education"]["field_of_study"] is None


def test_worker_profile_keeps_real_zero_and_deduplicates_lists():
    payload = _full_profile()
    payload["experience"]["years_in_current_occupation"] = 0
    payload["mobility"]["radius_miles"] = 0
    payload["credentials"] += [" state pesticide applicator credential "]
    payload["skills"] += ["customer SERVICE"]
    profile = validate_worker_profile(payload)
    assert profile["experience"]["years_in_current_occupation"] == 0
    assert profile["mobility"]["radius_miles"] == 0
    assert profile["credentials"] == ["State pesticide applicator credential"]
    assert profile["skills"] == ["Customer service", "Route scheduling", "Pest identification"]


@pytest.mark.parametrize("path, value", [
    ("experience", {"years_in_current_occupation": -1}),
    ("mobility", {"radius_miles": 1001}),
    ("wage", {"minimum_annual": 2000001}),
])
def test_worker_profile_rejects_unreasonable_numeric_values(path, value):
    with pytest.raises(WorkerProfileValidationError):
        validate_worker_profile({"profile_version": "v1", path: value})


def test_worker_profile_rejects_invalid_version_code_and_limits():
    payload = _full_profile()
    payload["profile_version"] = "v2"
    payload["current_occupation"]["occupation_code"] = "Pest control"
    payload["skills"] = ["x" * 121]
    payload["preferences"]["notes"] = "x" * 1001
    with pytest.raises(WorkerProfileValidationError) as exc:
        validate_worker_profile(payload)
    assert set(exc.value.errors) >= {"profile_version", "current_occupation.occupation_code", "skills", "preferences.notes"}


def test_worker_profile_contract_contains_no_assessment_fields_or_legacy_imports():
    profile = validate_worker_profile(_full_profile())
    serialized = json.dumps(profile).lower()
    source = (ROOT / "gvai/postlabor/worker_profile.py").read_text()
    for prohibited in ("score", "fit", "rank", "recommendation", "qualification", "transferability", "retraining_burden", "geographic_opportunity", "confidence"):
        assert prohibited not in serialized
    assert "worker_assessment" not in source
    assert "market_recommender" not in source


def test_worker_profile_validation_api_never_persists_or_echoes_invalid_values():
    client = api_service.app.test_client()
    valid = client.post("/api/worker/profile/validate", json=_full_profile())
    invalid = client.post("/api/worker/profile/validate", json={"profile_version": "v1", "skills": ["x" * 121]})
    malformed = client.post("/api/worker/profile/validate", data="{", content_type="application/json")
    assert valid.status_code == 200
    assert valid.get_json()["profile"]["skills"][0] == "Customer service"
    assert invalid.status_code == 400
    assert invalid.get_json() == {"ok": False, "errors": ["skills"]}
    assert "x" * 121 not in json.dumps(invalid.get_json())
    assert malformed.status_code == 400
    source = (ROOT / "gvai/api_service.py").read_text()
    endpoint = source[source.index("def api_worker_profile_validate"):source.index("def build_gv_runtime_policy")]
    assert "print(" not in endpoint
    assert "logger" not in endpoint


def test_worker_profile_ui_contract_is_local_only_and_explicit():
    html = (ROOT / "web/index.html").read_text()
    assert 'id="worker-profile-form"' in html
    assert 'gvai.workerProfile.v1' in html
    assert "localStorage.setItem(WORKER_PROFILE_STORAGE_KEY" in html
    assert "localStorage.removeItem(WORKER_PROFILE_STORAGE_KEY" in html
    assert "Your Worker Profile is stored only in this browser on this device." in html
    assert 'id="use-selected-occupation-btn"' in html
    assert "Use as my current occupation" in html
    assert "function useSelectedOccupationForWorkerProfile" in html
    assert "Worker Profile available for personal comparison." in html
    assert "try {" in html and "JSON.parse(localStorage.getItem(WORKER_PROFILE_STORAGE_KEY))" in html
    assert "isWorkerProfileV1(profile)" in html
    use_selected_start = html.index("function useSelectedOccupationForWorkerProfile")
    use_selected_end = html.index("document.getElementById(\"worker-profile-form\")", use_selected_start)
    use_selected = html[use_selected_start:use_selected_end]
    related_start = html.index("async function loadRelatedOccupationDrilldown")
    related_end = html.index("function renderTransitionComparison", related_start)
    related_drilldown = html[related_start:related_end]
    assert "currentOccupationCode" in use_selected
    assert "localStorage" not in use_selected
    assert "worker-profile" not in related_drilldown
    assert "WORKER_PROFILE_STORAGE_KEY" not in html[html.index("function workerProfileFromForm"):html.index("function isWorkerProfileV1")]
    for prohibited in ("name=\"email\"", "name=\"phone\"", "name=\"date-of-birth\"", "name=\"ssn\"", "name=\"street-address\""):
        assert prohibited not in html