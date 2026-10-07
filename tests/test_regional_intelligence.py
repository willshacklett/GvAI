from gvai.postlabor import regional_intelligence as intelligence
import pytest
from pathlib import Path


def region_fixture():
    return {"supported": True, "data_available": True, "state": "Tennessee", "county": "Rutherford County",
            "state_fips": "47", "county_fips": "149", "latitude": 35.85, "longitude": -86.4,
            "acs_year": 2024, "population": 363000, "labor_force": 200000, "unemployed": 8000,
            "unemployment_rate": 4, "median_household_income": 80000, "median_home_value": 400000,
            "home_value_to_income_ratio": 5, "occupation_profile": {"data_available": False}}


def test_shared_identity_and_source_metadata():
    result = intelligence.build_regional_intelligence(region_fixture())
    assert result["region"]["id"] == "US:county:47149"
    assert result["region"]["label"] == "Rutherford County, Tennessee"
    assert result["metrics"]["population"]["classification"] == "source_statistic"
    assert result["metrics"]["home_value_to_income_ratio"]["classification"] == "derived_metric"
    assert result["sources"]["acs"]["vintage"] == 2024
    assert result["sources"]["stex"]["vintage"] is None
    assert result["freshness"]["source_last_updated"] is None


def test_partial_data_never_manufactures_scores_or_zeros():
    result = intelligence.build_regional_intelligence(region_fixture())
    assert result["availability"]["status"] == "partial"
    assert result["metrics"]["population"]["value"] == 363000
    for key in ("stex_coverage", "automation_exposure", "stability_index", "job_displacement", "industry_concentration", "economic_resilience"):
        assert result["metrics"][key]["value"] is None
        assert result["metrics"][key]["availability"] == "unavailable"


def test_stex_is_partial_audited_exposure_not_displacement_probability():
    signal = {"status": "known", "values": {"coverage_percentage": 36.6, "covered_occupation_stex": 42,
              "stex_covered_employment": 36600, "total_employment": 100000, "source_year": 2025}}
    result = intelligence.build_regional_intelligence(region_fixture(), stex_signal={"id": "regional_stex_coverage", "explanation": "Audited subset", **signal})
    assert result["metrics"]["stex_coverage"]["value"] == 36.6
    assert result["sources"]["oews"]["vintage"] == 2025
    assert "not percent automatable" in result["metrics"]["automation_exposure"]["method"]
    assert result["metrics"]["job_displacement"]["value"] is None


def test_region_is_resolved_once_and_stex_failure_is_partial(monkeypatch):
    calls = []
    def resolve(**kwargs):
        calls.append(kwargs)
        return {**region_fixture(), "oews_area_code": "34980"}
    def fail(*args, **kwargs):
        raise RuntimeError("private packaged error")
    monkeypatch.setattr(intelligence, "resolve_us_region", resolve)
    monkeypatch.setattr(intelligence, "_regional_stex_signal", fail)
    result = intelligence.synthesize_regional_intelligence(latitude=35.85, longitude=-86.4)
    assert len(calls) == 1
    assert result["metrics"]["population"]["value"] == 363000
    assert "private packaged error" not in str(result)


def test_state_and_country_have_stable_ids_without_county_data():
    for scope, region, expected in (
        ("state", {"supported": True, "state_fips": "47", "state": "Tennessee"}, "US:state:47"),
        ("country", {"supported": True, "country": "United States"}, "US:country"),
    ):
        result = intelligence.build_regional_intelligence(region, scope=scope)
        assert result["region"]["id"] == expected
        assert result["metrics"]["population"]["value"] is None
        assert result["availability"]["status"] == "unavailable"


def test_invalid_source_numbers_are_unavailable():
    result = intelligence.build_regional_intelligence({**region_fixture(), "population": -666666666, "labor_force": float("nan")})
    assert result["metrics"]["population"]["value"] is None
    assert result["metrics"]["labor_force"]["value"] is None
    assert result["metrics"]["unemployment_rate"]["value"] is None
    assert result["metrics"]["labor_availability"]["value"] is None


def test_no_audited_employment_does_not_mean_zero_exposure():
    signal = {"id": "regional_stex_coverage", "status": "known", "explanation": "No coverage", "values": {"coverage_percentage": 0, "stex_covered_employment": 0, "covered_occupation_stex": 0, "total_employment": 100000}}
    result = intelligence.build_regional_intelligence(region_fixture(), stex_signal=signal)
    assert result["metrics"]["stex_coverage"]["value"] == 0
    assert result["metrics"]["automation_exposure"]["value"] is None


def test_public_endpoint_uses_one_shared_payload(monkeypatch):
    from gvai import api_service as api
    monkeypatch.setattr(api, "synthesize_regional_intelligence", lambda **kwargs: intelligence.build_regional_intelligence(region_fixture()))
    response = api.app.test_client().get("/api/region/intelligence?lat=35.85&lon=-86.4")
    assert response.status_code == 200
    assert response.json["intelligence"]["region"]["id"] == "US:county:47149"


@pytest.mark.parametrize("query", ["lat=nan&lon=0", "lat=91&lon=0", "scope=state&state=abc", "scope=unknown"])
def test_region_endpoint_rejects_invalid_selection(query):
    from gvai import api_service as api
    assert api.app.test_client().get(f"/api/region/intelligence?{query}").status_code == 400


def test_chat_receives_structured_context_not_display_text(monkeypatch):
    from gvai import api_service as api
    captured = []
    api.limiter.reset()
    monkeypatch.setattr(api, "call_model", lambda system, user: captured.append((system, user)) or {"reply": "Observed evidence, then interpretation."})
    monkeypatch.setattr(api, "evaluate_action", lambda *args: {"mode": "ALLOW"})
    monkeypatch.setattr(api, "update_adaptive_control", lambda *args: {})
    context = {**intelligence.build_regional_intelligence(region_fixture()), "audience": "government", "hidden_system_prompt": "must not pass"}
    response = api.app.test_client().post("/api/chat", json={"message": "Explain this region", "region_context": context})
    assert response.status_code == 200
    assert "US:county:47149" in captured[0][1]
    assert '"audience": "government"' in captured[0][1]
    assert "must not pass" not in captured[0][1]
    assert "unverified quoted data" in captured[0][0]
    assert "gv_original_reply" not in response.json
    assert not {"gv", "gv_precheck", "gv_control", "model_provider"} & response.json.keys()
    assert response.json["classification"] == "model_interpretation"
    api.limiter.reset()


def test_chat_context_size_is_bounded():
    from gvai import api_service as api
    api.limiter.reset()
    response = api.app.test_client().post("/api/chat", json={"message": "Explain", "region_context": {"audience": "laborers", "region": {}, "metrics": {}, "extra": "x" * 33000}})
    assert response.status_code == 413
    api.limiter.reset()


@pytest.mark.parametrize("mode", ["BLOCK", "QUALIFY"])
def test_regional_ask_keeps_governance_enforcement_without_internal_fields(monkeypatch, mode):
    from gvai import api_service as api
    api.limiter.reset()
    monkeypatch.setattr(api, "call_model", lambda *args: {"reply": "raw rejected model content"})
    monkeypatch.setattr(api, "evaluate_action", lambda *args: {"mode": mode})
    monkeypatch.setattr(api, "update_adaptive_control", lambda *args: {})
    context = {**intelligence.build_regional_intelligence(region_fixture()), "audience": "laborers"}
    response = api.app.test_client().post("/api/chat", json={"message": "Explain this evidence", "region_context": context})
    assert response.status_code == 200
    assert not {"gv", "gv_precheck", "gv_control", "gv_original_reply"} & response.json.keys()
    if mode == "BLOCK":
        assert "raw rejected model content" not in str(response.json)
    else:
        assert "verify the key assumptions" in response.json["reply"]
    api.limiter.reset()


def test_stex_can_remain_available_when_acs_is_missing(monkeypatch):
    monkeypatch.setattr(intelligence, "resolve_us_region", lambda **kwargs: {"supported": True, "state_fips": "47", "county_fips": "149", "data_available": False})
    calls = []
    def stex(area, **kwargs):
        calls.append(area)
        return {"status": "known", "id": "regional_stex_coverage", "explanation": "Audited subset", "values": {"coverage_percentage": 36.6, "source_year": 2025, "stex_covered_employment": 36600, "total_employment": 100000}}
    monkeypatch.setattr(intelligence, "_regional_stex_signal", stex)
    result = intelligence.synthesize_regional_intelligence(latitude=35.85, longitude=-86.4)
    assert calls == ["0034980"]
    assert result["metrics"]["population"]["value"] is None
    assert result["metrics"]["stex_coverage"]["value"] == 36.6
    assert result["availability"]["status"] == "partial"


def test_nonfinite_context_is_rejected_before_generation():
    from gvai import api_service as api
    api.limiter.reset()
    response = api.app.test_client().post("/api/chat", json={"message": "Explain", "region_context": {"audience": "government", "region": {}, "metrics": {"value": float("nan")}}})
    assert response.status_code == 400
    api.limiter.reset()


@pytest.mark.parametrize("scope", ["county", "state"])
def test_workforce_failure_does_not_erase_acs_baseline(monkeypatch, scope):
    from gvai.postlabor import region_intel
    monkeypatch.setenv("CENSUS_API_KEY", "synthetic-test-key")
    calls = []
    class Response:
        headers = {"content-type": "application/json"}
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): pass
        def json(self): return self.payload
    def get(url, **kwargs):
        calls.append(kwargs["timeout"])
        if "geocoder" in url:
            return Response({"result": {"geographies": {"Counties": [{"COUNTY": "149", "NAME": "Rutherford County"}], "States": [{"STATE": "47", "NAME": "Tennessee"}]}}})
        return Response([["NAME", "B01003_001E", "B23025_003E", "B23025_005E", "B19013_001E", "B25077_001E", "B01002_001E"], ["Tennessee", "363000", "200000", "8000", "80000", "400000", "36"]])
    def fail(**kwargs): raise RuntimeError("private subject-table error")
    monkeypatch.setattr(region_intel.requests, "get", get)
    monkeypatch.setattr(region_intel, "build_county_occupation_profile", fail)
    monkeypatch.setattr(region_intel, "build_aggregate_occupation_profile", fail)
    if scope == "county":
        region = region_intel.resolve_us_region(35.85, -86.4, request_timeout=7)
    else:
        region = region_intel.resolve_us_aggregate_region(scope="state", state_fips="47", request_timeout=7)
    result = intelligence.build_regional_intelligence(region, scope=scope)
    assert result["metrics"]["population"]["value"] == 363000
    assert result["availability"]["sections"]["workforce"]["status"] == "unavailable"
    assert all(timeout == 7 for timeout in calls)
    assert "private subject-table" not in str(result)


def test_regional_ui_uses_shared_model_not_demo_statistics():
    html = (Path(__file__).resolve().parents[1] / "web/index.html").read_text()
    profiles = html[html.index("const profiles = ["):html.index("const globalProfile")]
    assert "score:" not in profiles
    assert "population:" not in profiles
    assert "automation:" not in profiles
    selection = html[html.index("async function loadRegionalData("):html.index("function flyToProfile")]
    assert "/api/region/intelligence" in selection
    assert "void loadRegionalSTEX" not in selection
    assert "void loadRegionalLaborIntelligence" not in selection
    assert "invalidateRegionDependentEvidence()" in selection
    invalidation = html[html.index("function invalidateRegionDependentEvidence()"):html.index("function flyToProfile")]
    assert "activeBusinessWorkforceRequestId += 1" in invalidation
    assert "activeLiveJobsRequestId += 1" in invalidation
    assert selection.count("if (requestId !== activeRegionRequestId) return;") >= 2
    for audience in ("laborers", "business", "government"):
        assert f'data-regional-brief data-audience="{audience}"' in html
    assert 'id="regional-ask-form"' in html
    guide = (Path(__file__).resolve().parents[1] / "web/intelligence-guide.js").read_text()
    assert "requestBody(message, context, model ? root.GVAIRegional.contextForChat(model, regional.get().audience) : null)" in guide
    assert "region_context: regionalContext" in guide
    assert "intelligence_session: context" in guide
    assert "Input assumptions" in html
    assert "Current published baseline" in html
    assert "Scenario change" in html
    assert "Potential effect" in html
    assert "worker-task-audit-slot" in html


def test_all_available_metrics_have_classification_source_and_method():
    result = intelligence.build_regional_intelligence(region_fixture())
    for metric in result["metrics"].values():
        assert metric["classification"] in {"source_statistic", "derived_metric"}
        assert metric["method"]
        if metric["value"] is not None:
            assert metric["source_ids"]
            assert all(source in result["sources"] for source in metric["source_ids"])


@pytest.mark.parametrize("scope", ["county", "state", "country"])
@pytest.mark.parametrize("failure", ["timeout", "invalid_json", "wrong_shape", "wrong_geography", "html"])
def test_acs_failures_preserve_selection_without_misattributing_values(monkeypatch, scope, failure):
    from gvai.postlabor import region_intel
    monkeypatch.setenv("CENSUS_API_KEY", "synthetic-test-key")
    class Response:
        headers = {"content-type": "text/html" if failure == "html" else "application/json"}
        def raise_for_status(self): pass
        def json(self):
            if failure == "invalid_json": raise ValueError("private malformed response")
            if failure == "wrong_shape": return {"error": "not a table"}
            return [["NAME", "B01003_001E", "state", "county", "us"], ["Wrong geography", "999999", "26", "163", "2"]]
    def get(url, **kwargs):
        if "geocoder" in url:
            class Geography(Response):
                def json(self):
                    return {"result": {"geographies": {"Counties": [{"COUNTY": "149", "NAME": "Rutherford County"}], "States": [{"STATE": "47", "NAME": "Tennessee"}]}}}
            return Geography()
        if failure == "timeout": raise region_intel.requests.Timeout("private upstream timeout")
        return Response()
    monkeypatch.setattr(region_intel.requests, "get", get)
    region = region_intel.resolve_us_region(35.85, -86.4) if scope == "county" else region_intel.resolve_us_aggregate_region(scope=scope, state_fips="47" if scope == "state" else None)
    result = intelligence.build_regional_intelligence(region, scope=scope)
    assert result["region"]["id"] == {"county": "US:county:47149", "state": "US:state:47", "country": "US:country"}[scope]
    assert result["metrics"]["population"]["value"] is None
    assert "private" not in str(result)


@pytest.mark.parametrize("code", ["00", "03", "99", "4x", "４７", "047"])
def test_invalid_state_fips_is_rejected(code):
    from gvai import api_service as api
    assert api.app.test_client().get("/api/region/intelligence", query_string={"scope": "state", "state": code}).status_code == 400


def test_fips_identity_is_canonical_and_missing_county_never_becomes_state():
    assert intelligence.build_regional_intelligence({"supported": True, "state_fips": "1", "county_fips": "1"})["region"]["id"] == "US:county:01001"
    assert intelligence.build_regional_intelligence({"supported": True, "state_fips": "47", "county_fips": "000"})["region"]["id"] is None
    assert intelligence.build_regional_intelligence({"supported": True, "state_fips": "99", "county_fips": "149"})["region"]["id"] is None


@pytest.mark.parametrize("scope", ["state", "country"])
def test_aggregate_region_never_inherits_county_stex(scope):
    result = intelligence.build_regional_intelligence({**region_fixture(), "oews_area_code": "0034980"}, scope=scope,
        stex_signal={"status": "known", "explanation": "Wrong scope", "values": {"coverage_percentage": 99, "oews_area_code": "0034980"}})
    assert result["metrics"]["stex_coverage"]["value"] is None
    assert result["region"]["county_fips"] is None
    assert result["region"]["oews_area_code"] is None


def test_stex_area_mismatch_is_not_published_as_county_evidence():
    result = intelligence.build_regional_intelligence({**region_fixture(), "oews_area_code": "0034980"},
        stex_signal={"status": "known", "explanation": "Wrong area", "values": {"coverage_percentage": 99, "oews_area_code": "0032820"}})
    assert result["metrics"]["stex_coverage"]["value"] is None
    assert result["sources"]["acs"]["geography"]["type"] == "county"
    assert result["sources"]["oews"]["geography"]["id"] == "0034980"


def test_inconsistent_derived_baselines_and_missing_workforce_denominator_are_unknown():
    result = intelligence.build_regional_intelligence({**region_fixture(), "unemployment_rate": 99, "home_value_to_income_ratio": 100,
        "occupation_profile": {"data_available": True, "groups": [{"label": "Service", "employed": 100, "share_percent": 50}]}})
    assert result["metrics"]["unemployment_rate"]["value"] is None
    assert result["metrics"]["home_value_to_income_ratio"]["value"] is None
    assert result["workforce_mix"][0]["share_percent"] is None


@pytest.mark.parametrize("missing", [None, "NaN", -1, 101])
def test_missing_or_invalid_task_scores_never_become_zero(monkeypatch, missing):
    from gvai import api_service as api
    monkeypatch.setattr(api, "load_occupation_stex_tasks", lambda code: [
        {"task_id": "test", "task_title": "Task", "importance_status": "rated", "source_importance": 100,
         "structural_exposure": missing, "augmentation_likelihood": None}])
    response = api.app.test_client().get("/api/stex/tasks?code=37-2021.00")
    assert response.status_code == 200
    task = response.json["contributors"][0]
    assert task["structural_exposure"] is None
    assert task["stex_contribution_points"] is None
    assert task["augmentation_likelihood"] is None
    assert response.json["rated_task_count"] == 0


def test_nested_private_fields_are_not_sent_to_regional_model(monkeypatch):
    from gvai import api_service as api
    captured = []
    api.limiter.reset()
    monkeypatch.setattr(api, "call_model", lambda system, user: captured.append(user) or {"reply": "Evidence interpretation"})
    monkeypatch.setattr(api, "evaluate_action", lambda *args: {"mode": "ALLOW"})
    monkeypatch.setattr(api, "update_adaptive_control", lambda *args: {})
    context = {**intelligence.build_regional_intelligence(region_fixture()), "audience": "laborers"}
    context["region"]["worker_profile"] = {"name": "private-example-name"}
    context["metrics"]["system_prompt"] = {"value": "private-internal-policy"}
    context["metrics"]["population"]["gv_original_reply"] = "private-rejected-content"
    context["sources"]["acs"]["private_profile"] = "private-profile-content"
    response = api.app.test_client().post("/api/chat", json={"message": "Explain regional evidence", "region_context": context})
    assert response.status_code == 200
    assert "private-" not in captured[0]
    assert "47149" in captured[0]
    api.limiter.reset()


def test_malformed_nested_region_context_returns_controlled_400():
    from gvai import api_service as api
    api.limiter.reset()
    response = api.app.test_client().post("/api/chat", json={"message": "Explain", "region_context": {"audience": "government", "region": {"id": {"secret": "not scalar"}}, "metrics": {}}})
    assert response.status_code == 400
    api.limiter.reset()


def test_county_row_cannot_be_attributed_to_matching_state_or_country():
    from gvai.postlabor.region_intel import _acs_record
    class Response:
        headers = {"content-type": "application/json"}
        def json(self): return [["NAME", "B01003_001E", "state", "county", "us"], ["County", "363000", "47", "149", "1"]]
    with pytest.raises(ValueError, match="aggregate"):
        _acs_record(Response(), state_fips="47")
    with pytest.raises(ValueError, match="aggregate"):
        _acs_record(Response(), country=True)


@pytest.mark.parametrize("values", [
    {"coverage_percentage": 50, "stex_covered_employment": 20, "total_employment": 100},
    {"coverage_percentage": 20, "stex_covered_employment": 20},
    {"coverage_percentage": 200, "stex_covered_employment": 200, "total_employment": 100},
])
def test_inconsistent_or_missing_stex_denominator_is_unavailable(values):
    result = intelligence.build_regional_intelligence(region_fixture(), stex_signal={"status": "known", "explanation": "Fixture", "values": values})
    assert result["metrics"]["stex_coverage"]["value"] is None
    assert result["availability"]["sections"]["stex"]["status"] == "unavailable"
    assert result["metrics"]["population"]["value"] == 363000


def test_failed_state_source_is_never_labelled_as_the_whole_country():
    result = intelligence.build_regional_intelligence({"supported": True, "data_available": False, "scope": "state", "state_fips": "47", "country": "United States"}, scope="state")
    assert result["region"]["id"] == "US:state:47"
    assert result["region"]["label"] == "US state 47"
    assert result["sources"]["acs"]["geography"]["type"] == "state"