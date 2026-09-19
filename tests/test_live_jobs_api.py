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


def test_live_jobs_api_keeps_unsupported_country_explicit():
    client = api_service.app.test_client()
    response = client.get(
        "/api/worker/live-jobs?country=CA&occupation=NOC-21231"
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "unsupported_country"
    assert payload["openings"] == []