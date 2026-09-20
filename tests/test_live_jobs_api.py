from gvai import api_service
from gvai.postlabor.live_jobs import LiveJobsRegistry


def test_live_jobs_api_uses_public_query_context_and_explicit_unavailable_state(monkeypatch):
    captured = {}

    class Registry:
        def search(self, context, *, occupation=None):
            captured["context"] = context
            captured["occupation"] = occupation
            return LiveJobsRegistry().search(context, occupation=occupation)

    monkeypatch.setattr(api_service, "DEFAULT_LIVE_JOBS_REGISTRY", Registry())
    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/live-jobs?country=US&occupation=15-1252.00"
        "&occupation_title=Software%20Developers&location=Nashville"
        "&lat=36.1&lon=-86.7"
        "&wages=private&skills=private&credentials=private"
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "provider_unavailable"
    assert payload["capability"] == "live_job_openings"
    assert payload["provider_configured"] is False
    assert captured["context"].location == "Nashville"
    assert captured["occupation"].provider_occupation_code == "15-1252.00"
    assert not hasattr(captured["context"], "worker_profile")
    assert not hasattr(captured["context"], "wages")
    assert not hasattr(captured["context"], "skills")
    assert not hasattr(captured["context"], "credentials")


def test_live_jobs_api_keeps_unsupported_country_explicit():
    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/live-jobs?country=CA&occupation=NOC-21231"
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "unsupported_country"
    assert payload["openings"] == []


def test_live_jobs_api_uses_only_explicit_public_filters(monkeypatch):
    captured = {}

    class Registry:
        def search(self, context, *, occupation=None):
            captured.update(vars(context))
            return LiveJobsRegistry().search(context, occupation=occupation)

    monkeypatch.setattr(api_service, "DEFAULT_LIVE_JOBS_REGISTRY", Registry())
    response = api_service.app.test_client().get(
        "/api/worker/live-jobs?country=US&remote_only=true&radius=20"
        "&schedule_type_code=1&posted_within_days=7"
        "&worker_wage=90000&education=private&experience=private"
        "&saved_occupations=private&personal_skills=private&preferences=private"
        "&investigation_history=private&profile_name=private"
    )

    assert response.status_code == 200
    assert captured["remote_only"] is True
    assert captured["radius"] == 20.0
    assert captured["schedule_type_code"] == "1"
    assert captured["posted_within_days"] == 7
    assert set(captured) == {
        "country_code", "occupation_code", "location", "latitude", "longitude",
        "radius", "remote_only", "schedule_type_code", "posted_within_days",
    }


def test_live_jobs_api_rejects_invalid_public_filters():
    client = api_service.app.test_client()
    assert client.get("/api/worker/live-jobs?remote_only=maybe").status_code == 400
    assert client.get("/api/worker/live-jobs?radius=0").status_code == 400
    assert client.get("/api/worker/live-jobs?posted_within_days=61").status_code == 400