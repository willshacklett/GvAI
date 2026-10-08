import json

import pytest

from gvai import decision_intelligence as decision
from gvai.intelligence_session import sanitize_session, validate_actions
from gvai.postlabor.regional_intelligence import build_regional_intelligence


A, B = "US:county:47149", "US:county:47065"


def criterion(key, value="user-stated preference", direction="higher", priority="primary"):
    return {"key": key, "value": value, "direction": direction, "priority": priority}


def investigation(**changes):
    return {"schema_version": decision.VERSION, "type": "regional_comparison",
            "question": "Where should we expand?", "criteria": [
                criterion("geography", "Tennessee", "inspect", "constraint"),
                criterion("labor_force"),
                criterion("housing_pressure", "less housing pressure", "lower", "secondary")],
            "candidates": [{"region_id": A, "status": "shortlisted", "reason": None},
                           {"region_id": B, "status": "shortlisted", "reason": None}], **changes}


def model(identity, labor, home):
    return build_regional_intelligence({
        "supported": True, "state": "Tennessee", "county": "Rutherford County" if identity == A else "Hamilton County",
        "state_fips": "47", "county_fips": "149" if identity == A else "065",
        "latitude": 35.85 if identity == A else 35.2, "longitude": -86.4 if identity == A else -85.2,
        "acs_year": 2024, "labor_force": labor, "median_household_income": 80000,
        "median_home_value": home, "home_value_to_income_ratio": home / 80000,
    })


def evidence():
    return [model(A, 200000, 400000), model(B, 100000, 240000)]


def session(value):
    return {"schema_version": "gvai.intelligence-session.v1", "audience": "business",
            "selected_region_id": A, "comparison_ids": [A, B], "occupation_code": None,
            "regions": [{"id": item["region"]["id"], "latitude": item["region"]["latitude"],
                         "longitude": item["region"]["longitude"]} for item in evidence()],
            "investigation": value}


@pytest.mark.parametrize("kind", sorted(decision.TYPES))
def test_investigation_types_are_explicit_and_preserve_criteria(kind):
    result = sanitize_session(session(investigation(type=kind)))["investigation"]
    assert result["type"] == kind
    assert result["criteria"] == investigation()["criteria"]
    assert result["candidates"] == investigation()["candidates"]


def test_recommendation_changes_with_visible_priority_not_a_universal_score():
    inv = investigation()
    first = decision.assess(inv, evidence(), [A, B])
    assert first["leader_region_id"] == A
    assert first["status"] == "provisional"
    assert first["region_reads"][A]["tradeoffs"] == [{"criterion": "housing_pressure", "occupation_code": None}]
    assert first["region_reads"][B]["supports"] == [{"criterion": "housing_pressure", "occupation_code": None}]
    assert "at most 3" in first["region_reads"][A]["could_move_up"][0]
    assert "labor force" in first["region_reads"][A]["could_eliminate"][0]
    inv["criteria"][1]["priority"] = "secondary"
    inv["criteria"][2]["priority"] = "primary"
    second = decision.assess(inv, evidence(), [A, B])
    assert second["leader_region_id"] == B
    assert all("score" not in signal for signal in second["signals"])
    assert first["could_change_if"] and "priority" in first["could_change_if"][0]
    assert "unverified" in second["current_read"]
    assert first["signals"][0]["values"][0]["classification"] == "source_statistic"
    assert first["signals"][1]["values"][0]["classification"] == "derived_metric"
    assert first["classification"] == "model_interpretation"


def test_conflicting_primaries_and_equal_values_do_not_force_a_winner():
    inv = investigation()
    inv["criteria"][2]["priority"] = "primary"
    assert decision.assess(inv, evidence(), [A, B])["leader_region_id"] is None
    models = evidence()
    models[1]["metrics"]["labor_force"]["value"] = 200000
    assert decision.assess(investigation(), models, [A, B])["leader_region_id"] is None


@pytest.mark.parametrize("condition", ["missing", "negative", "nan", "unavailable", "vintage", "scope", "source_missing"])
def test_missing_or_incomparable_evidence_is_not_zero_or_a_winner(condition):
    models = evidence()
    metric = models[1]["metrics"]["labor_force"]
    if condition == "missing":
        metric["value"] = None
    elif condition == "negative":
        metric["value"] = -1
    elif condition == "nan":
        metric["value"] = float("nan")
    elif condition == "unavailable":
        metric.update(value=0, availability="unavailable")
    elif condition == "vintage":
        models[1]["sources"]["acs"]["vintage"] = 2023
    elif condition == "scope":
        models[1]["region"]["type"] = "state"
    elif condition == "source_missing":
        metric["source_ids"] = []
    result = decision.assess(investigation(), models, [A, B])
    assert result["leader_region_id"] is None
    assert result["signals"][0]["comparable"] is False
    assert result["evidence_gaps"]
    if condition in {"missing", "negative", "nan", "unavailable"}:
        assert result["signals"][0]["values"][1]["value"] is None


def test_observed_zero_is_not_misrepresented_as_missing():
    models = evidence()
    models[1]["metrics"]["labor_force"]["value"] = 0
    result = decision.assess(investigation(), models, [A, B])
    assert result["signals"][0]["values"][1]["value"] == 0
    assert result["signals"][0]["comparable"] is True


def test_clarification_targets_only_material_criteria_and_remembers_supplied_ones():
    inv = investigation(type="hiring_workforce", criteria=[])
    read = decision.assess(inv, [], [])
    assert read["missing_criteria"] == ["geography", "occupations", "priority"]
    assert "geographic" in read["clarification"]
    inv["criteria"].append(criterion("geography", "Nashville corridor", "inspect", "constraint"))
    read = decision.assess(inv, [], [])
    assert read["missing_criteria"] == ["occupations", "priority"]
    assert "technician" in read["clarification"]
    inv["criteria"].extend([criterion("occupations", [{"code": "37-2021.00", "workers": 30}], "inspect", "constraint"), criterion("labor_force")])
    assert decision.assess(inv, evidence(), [])["clarification"] is None


def test_radius_jobs_composition_and_stex_are_gaps_not_synthetic_rankings():
    inv = investigation(criteria=[criterion("geography", "TN"), criterion("distance_radius", {"miles": 100, "center": "Nashville"}),
                                  criterion("current_jobs"), criterion("occupational_composition"), criterion("stex")])
    result = decision.assess(inv, evidence(), [A, B])
    assert result["leader_region_id"] is None
    assert {gap["criterion"] for gap in result["evidence_gaps"]} == {
        "geography", "distance_radius", "current_jobs", "occupational_composition", "stex"}


@pytest.mark.parametrize("specificity", ["exact", "broader", "unavailable"])
def test_occupation_comparison_requires_exact_match_area_and_known_vintage(specificity):
    models = evidence()
    for index, item in enumerate(models):
        item["occupation_evidence_by_code"] = {"37-2021.00": {
            "geography": {"type": "oews_labor_market_area", "id": f"fixture-{index}"},
            "oews_specificity": {"status": specificity},
            "employment": {"status": "known", "employment": 1000 + index * 100,
                           "source": "BLS OEWS fixture", "source_year": 2025},
            "wage": {"status": "known", "median_annual_wage": 50000 + index * 1000,
                     "source": "BLS OEWS fixture", "source_year": 2025}}}
    inv = investigation(type="business_expansion", criteria=[
        criterion("geography", "TN"), criterion("occupations", [{"code": "37-2021.00", "workers": 30}], "inspect", "constraint"),
        criterion("workforce_availability"), criterion("wage_level", direction="lower", priority="secondary")])
    result = decision.assess(inv, models, [A, B])
    assert result["leader_region_id"] == (B if specificity == "exact" else None)
    assert "not vacancies" in result["signals"][0]["note"]
    if specificity == "exact":
        models[0]["occupation_evidence_by_code"]["37-2021.00"]["geography"]["id"] = None
        assert decision.assess(inv, models, [A, B])["leader_region_id"] is None


def test_rejected_candidate_cannot_drive_recommendation_and_reason_is_interpretation():
    inv = investigation()
    inv["candidates"][0].update(status="rejected", reason="Housing tradeoff not acceptable.")
    read = decision.assess(inv, evidence(), [A, B])
    assert read["leader_region_id"] is None
    assert read["region_reads"][A]["reason"] == "Housing tradeoff not acceptable."
    assert read["region_reads"][A]["classification"] == "model_interpretation"


def test_government_read_is_neutral_monitoring_not_a_jurisdiction_ranking():
    read = decision.assess(investigation(type="government_monitoring"), evidence(), [A, B])
    assert read["leader_region_id"] is None
    assert read["status"] == "monitoring"
    assert "No time-series change" in read["current_read"]
    assert "displacement forecast" in read["current_read"]


@pytest.mark.parametrize("bad", [
    [{"key": "profile", "value": "PRIVATE_SENTINEL", "direction": "higher", "priority": "primary"}],
    [criterion("labor_force", direction="best")], [criterion("labor_force", priority=[])],
    [criterion("labor_force"), criterion("labor_force")],
    [criterion("occupations", [{"code": "37-2021.00", "workers": True}])],
    [criterion("occupations", [{"code": "https://example.com", "workers": 30}])],
    [criterion("occupations", [{"code": "37-2021.00", "workers": 30, "private_wage": 62000}])],
    [criterion("distance_radius", {"miles": False, "center": "Nashville"})],
    [criterion("distance_radius", {"miles": float("inf"), "center": "Nashville"})],
    [criterion("distance_radius", {"miles": 100, "center": "Nashville", "url": "https://example.org"})],
    [criterion("user_priority", "x" * 401)],
])
def test_malformed_criteria_never_gain_action_authority(bad):
    assert validate_actions([{"type": "set_criteria", "criteria": bad}], {A, B}) == ([], 1)
    with pytest.raises(ValueError):
        decision.validate_criteria(bad)


def test_candidate_contract_requires_known_identity_rejection_reason_and_bounds():
    for candidates in [
        [{"region_id": A, "status": "rejected", "reason": ""}],
        [{"region_id": "unknown", "status": "candidate", "reason": None}],
        [{"region_id": A, "status": "candidate"}] * 9,
        [{"region_id": A, "status": "candidate"}] * 2,
    ]:
        with pytest.raises(ValueError):
            sanitize_session(session(investigation(candidates=candidates)))


def test_private_fields_and_client_authored_conclusions_are_not_transmitted():
    inv = investigation(worker_profile={"wage": "PRIVATE_SENTINEL"}, current_read="FABRICATED_WINNER",
                        decision_read={"leader_region_id": "FABRICATED_WINNER"})
    inv["candidates"][0]["private_notes"] = "PRIVATE_SENTINEL"
    sanitized = sanitize_session(session(inv))
    assert "PRIVATE_SENTINEL" not in json.dumps(sanitized)
    assert "FABRICATED_WINNER" not in json.dumps(sanitized)


@pytest.mark.parametrize("action", [
    {"type": "start_investigation", "investigation_type": "business_expansion", "question": "Open an office?"},
    {"type": "set_criteria", "criteria": [criterion("labor_force")]},
    {"type": "add_candidate", "query": "Springfield"},
    {"type": "add_candidate", "region_id": A},
    {"type": "remove_candidate", "region_id": A},
    {"type": "shortlist_candidate", "region_id": B},
    {"type": "reject_candidate", "region_id": A, "reason": "Housing tradeoff"},
    {"type": "focus_candidate", "region_id": B},
    {"type": "compare_candidates"},
])
def test_new_actions_keep_exact_allowlist(action):
    assert validate_actions([action], {A, B}) == ([action], 0)
    assert validate_actions([{**action, "code": "alert(1)"}], {A, B}) == ([], 1)


@pytest.fixture
def client(monkeypatch):
    from gvai import api_service as api
    api.limiter.reset()
    monkeypatch.setattr(api, "evaluate_action", lambda *args: {"mode": "ALLOW"})
    monkeypatch.setattr(api, "update_adaptive_control", lambda *args: {})
    yield api, api.app.test_client()
    api.limiter.reset()


def test_api_recomputes_read_and_continuation_has_no_model_action_authority(client, monkeypatch):
    api, http = client
    calls, occupations = [], []
    monkeypatch.setattr(api, "synthesize_regional_intelligence",
                        lambda latitude, longitude: evidence()[0 if latitude == 35.85 else 1])
    def public(**kwargs):
        occupations.append(kwargs["occupation_code"])
        return {"employment": {}, "wage": {}, "stex": {}, "oews_specificity": {"status": "unavailable"}}
    monkeypatch.setattr(api, "public_occupation_evidence", public)
    def model(system, content):
        calls.append((system, content))
        return {"reply": json.dumps({"reply": "Interpretation with tradeoffs", "actions": [{"type": "open_jobs"}]})}
    monkeypatch.setattr(api, "call_model", model)
    inv = investigation()
    inv["criteria"].append(criterion("occupations", [{"code": "37-2021.00", "workers": 30},
                                                   {"code": "41-3091.00", "workers": 5},
                                                   {"code": "11-1021.00", "workers": 3}], "inspect", "constraint"))
    response = http.post("/api/chat", json={"message": "Continue", "intelligence_session": session(inv), "continuation": True})
    assert response.status_code == 200
    assert response.json["actions"] == []
    assert response.json["decision_read"]["leader_region_id"] == A
    assert occupations == ["37-2021.00", "41-3091.00", "11-1021.00"] * 2
    supplied = json.loads(calls[0][1].split("INVESTIGATION_JSON:\n")[1])
    assert supplied["continuation"] is True
    assert supplied["DECISION_READ"] == response.json["decision_read"]
    assert "Capture only criteria the user actually stated" in calls[0][0]
    assert http.post("/api/chat", json={"message": "Continue", "continuation": "true"}).status_code == 400


def test_geocoder_disambiguates_real_provider_candidates_without_selecting_first(client, monkeypatch):
    api, http = client
    calls = []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return [{"lat": str(35 + index), "lon": "-86", "display_name": f"Springfield {index}",
                     "address": {"country_code": "us", "state": "Tennessee"}} for index in range(7)]
    def request(url, **kwargs):
        calls.append(kwargs["params"])
        return Response()
    monkeypatch.setattr(api.requests, "get", request)
    reply = http.get("/api/geocode?q=Springfield&candidates=1")
    assert reply.status_code == 200
    assert reply.json["requires_choice"] is True
    assert len(reply.json["candidates"]) == 5
    assert "latitude" not in reply.json
    assert calls[0]["limit"] == 5
    assert calls[0]["polygon_geojson"] == 0
    legacy = http.get("/api/geocode?q=Springfield")
    assert legacy.json["label"] == "Springfield 0"
    assert calls[1]["limit"] == 1
    assert calls[1]["polygon_geojson"] == 1


def test_geocoder_invalid_coordinates_fail_explicitly(client, monkeypatch):
    api, http = client
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return [{"lat": "NaN", "lon": "-86"}]
    monkeypatch.setattr(api.requests, "get", lambda *args, **kwargs: Response())
    reply = http.get("/api/geocode?q=Springfield&candidates=1")
    assert reply.status_code == 502
    assert reply.json["reason"] == "Place search is temporarily unavailable."
