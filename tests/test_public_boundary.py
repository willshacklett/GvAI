import os
import subprocess
import sys

import pytest

from gvai import api_service as api


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(api.app.config, "TESTING", True)
    api.limiter.reset()
    monkeypatch.setattr(api, "call_model", lambda *args: {"reply": "Safe reply"})
    monkeypatch.setattr(api, "evaluate_action", lambda *args: {"mode": "ALLOW"})
    monkeypatch.setattr(api, "update_adaptive_control", lambda *args: {})
    yield api.app.test_client()
    api.limiter.reset()


@pytest.mark.parametrize("message", ["x" * 8193, "\u00e9" * 4097, " " * 8193])
def test_chat_message_size_rejected(client, message):
    response = client.post("/api/chat", json={"message": message})
    assert response.status_code == 413
    assert response.json["ok"] is False
    assert "reason" in response.json


def test_chat_body_size_rejected(client):
    response = client.post("/api/chat", json={"message": "hello", "extra": "x" * 65536})
    assert response.status_code == 413
    assert response.json == {"ok": False, "reason": "Request is too large."}


@pytest.mark.parametrize("payload", [None, [], {"message": 123}, {"message": ""}])
def test_chat_requires_text(client, payload):
    assert client.post("/api/chat", json=payload).status_code == 400


@pytest.mark.parametrize("query", ["x" * 513, " " * 513, "\u00e9" * 257])
def test_geocode_query_size_rejected(client, query):
    response = client.get("/api/geocode", query_string={"q": query})
    assert response.status_code == 413
    assert response.json["ok"] is False


def test_local_browser_cors_requires_explicit_environment():
    result = subprocess.run([
        sys.executable, "-c",
        "from gvai.api_service import app; "
        "response = app.test_client().options('/api/chat', headers={'Origin':'http://localhost:8090','Access-Control-Request-Method':'POST'}); "
        "print(response.status_code, response.headers.get('Access-Control-Allow-Origin'))",
    ], env={**os.environ, "GVAI_CORS_ORIGINS": "http://localhost:8090", "GVAI_RATE_LIMIT_STORAGE_URI": "memory://"}, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "200 http://localhost:8090"


def test_untrusted_forwarded_header_cannot_bypass_limit(client, monkeypatch):
    monkeypatch.setitem(api.app.config, "CHAT_RATE_LIMIT", "1 per minute")
    assert client.post("/api/chat", json={"message": "hello"}).status_code == 200
    response = client.post("/api/chat", json={"message": "hello"}, headers={"X-Forwarded-For": "192.0.2.7"})
    assert response.status_code == 429


@pytest.mark.parametrize("origin", ["https://gvai.io", "https://www.gvai.io"])
def test_production_cors_and_preflight(client, origin):
    response = client.options("/api/chat", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == origin
    response = client.post("/api/chat", json={"message": "hello"}, headers={"Origin": origin})
    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == origin


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://localhost:8080"])
def test_unconfigured_browser_origin_rejected(client, origin):
    response = client.post("/api/chat", json={"message": "hello"}, headers={"Origin": origin})
    assert response.status_code == 403
    assert "Access-Control-Allow-Origin" not in response.headers


def test_nonbrowser_access_and_health(client):
    assert client.post("/api/chat", json={"message": "hello"}).status_code == 200
    assert client.get("/api/health").json["ok"] is True


@pytest.mark.parametrize("authorization", ["", "Bearer incorrect", "Bearer \u00e9"])
def test_enabled_review_writes_require_operator_token(client, monkeypatch, authorization):
    monkeypatch.setenv("GVAI_STEX_REVIEW_WRITES_ENABLED", "1")
    monkeypatch.setenv("GVAI_STEX_REVIEW_TOKEN", "synthetic-review-test-token")
    def must_not_write(*args):
        pytest.fail("unauthorized mutation reached approval code")
    monkeypatch.setattr(api, "approve_occupation", must_not_write)
    response = client.post("/api/stex/review/approve", json={}, headers={"Authorization": authorization})
    assert response.status_code == 403


def test_enabled_review_without_configured_token_fails_closed(client, monkeypatch):
    monkeypatch.setenv("GVAI_STEX_REVIEW_WRITES_ENABLED", "1")
    monkeypatch.delenv("GVAI_STEX_REVIEW_TOKEN", raising=False)
    assert client.post("/api/stex/review/approve", json={}).status_code == 403


@pytest.mark.parametrize("path,config", [
    ("/api/chat", "CHAT_RATE_LIMIT"), ("/api/geocode", "GEOCODE_RATE_LIMIT"),
])
def test_public_rate_limits_do_not_limit_health(client, monkeypatch, path, config):
    monkeypatch.setitem(api.app.config, config, "2 per minute")
    for attempt in range(2):
        if path.endswith("chat"):
            assert client.post(path, json={"message": "hello"}).status_code == 200
        else:
            assert client.get(path).status_code == 400
    response = client.post(path, json={"message": "hello"}) if path.endswith("chat") else client.get(path)
    assert response.status_code == 429
    assert response.json["ok"] is False
    assert "Retry-After" in response.headers
    assert client.get("/api/health").status_code == 200


def test_global_limit_spans_clients(client, monkeypatch):
    monkeypatch.setitem(api.app.config, "CHAT_GLOBAL_RATE_LIMIT", "1 per minute")
    assert client.post("/api/chat", json={"message": "hello"}).status_code == 200
    response = client.post("/api/chat", json={"message": "hello"}, environ_overrides={"REMOTE_ADDR": "192.0.2.1"})
    assert response.status_code == 429


def test_model_exception_sanitized_and_logged(client, monkeypatch, caplog):
    def fail(*args):
        raise RuntimeError("private provider implementation detail")
    monkeypatch.setattr(api, "call_model", fail)
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 502
    assert "private provider" not in response.get_data(as_text=True)
    assert "private provider" in caplog.text


def test_unhandled_exception_returns_json(client, monkeypatch, caplog):
    def fail(*args):
        raise RuntimeError("private policy detail")
    monkeypatch.setattr(api, "build_gv_runtime_policy", fail)
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 500
    assert response.json["ok"] is False
    assert "private policy" not in response.get_data(as_text=True)
    assert "private policy" in caplog.text


@pytest.mark.parametrize("path,dependency,reason", [
    ("housing-pressure", "resolve_state_county_housing_pressure", "Housing pressure lookup failed."),
    ("workforce-mix", "resolve_state_county_workforce_mix", "Workforce mix lookup failed."),
    ("labor-availability", "resolve_state_county_labor_availability", "Labor availability lookup failed."),
])
def test_regional_failures_preserve_safe_reason_and_log_details(client, monkeypatch, caplog, path, dependency, reason):
    def fail(*args):
        raise RuntimeError("private regional provider detail")
    monkeypatch.setattr(api, dependency, fail)
    response = client.get(f"/api/region/{path}?state=47")
    assert response.status_code == 500
    assert response.json["reason"] == reason
    assert "error" not in response.json
    assert "error_type" not in response.json
    assert "private regional" not in response.get_data(as_text=True)
    assert "private regional" in caplog.text


@pytest.mark.parametrize("mode", ["BLOCK", "QUALIFY", "ALLOW"])
def test_governance_never_returns_original_reply(client, monkeypatch, mode):
    monkeypatch.setattr(api, "evaluate_action", lambda *args: {"mode": mode})
    payload = api.attach_gv_conscience({"reply": "raw model reply", "gv_original_reply": "raw model reply"})
    assert "gv_original_reply" not in payload
    if mode == "BLOCK":
        assert "raw model reply" not in str(payload)
    response = client.post("/api/chat", json={"message": "hello"})
    assert "gv_original_reply" not in response.json