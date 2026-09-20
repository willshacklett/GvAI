from gvai import api_service
from gvai.postlabor.provider_registry import GlobalProviderRegistry, ProviderRegistration


class FakeAdapter:
    def __init__(self, configured):
        self.configured = configured
        self.api_key = "should-never-be-exposed"


def test_capabilities_endpoint_reports_unsupported_country():
    client = api_service.app.test_client()
    response = client.get("/api/worker/live-jobs/capabilities?country=ZZ")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["state"] == "unsupported"
    assert payload["providers"] == []


def test_capabilities_endpoint_rejects_malformed_country_code():
    client = api_service.app.test_client()
    response = client.get("/api/worker/live-jobs/capabilities?country=USA")
    payload = response.get_json()
    assert response.status_code == 400
    assert payload["ok"] is False


def test_capabilities_endpoint_reports_multi_provider_country_without_secrets(monkeypatch):
    registry = GlobalProviderRegistry([
        ProviderRegistration(
            country_code="US",
            provider="usajobs",
            capability="live_job_openings",
            priority=1,
            attribution="USAJOBS API",
            adapter=FakeAdapter(False),
        ),
        ProviderRegistration(
            country_code="US",
            provider="secondprovider",
            capability="live_job_openings",
            priority=2,
            attribution="Second Provider API",
            adapter=FakeAdapter(True),
        ),
    ])
    monkeypatch.setattr(api_service, "DEFAULT_PROVIDER_REGISTRY", registry)
    client = api_service.app.test_client()
    response = client.get("/api/worker/live-jobs/capabilities?country=US")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["state"] == "available"
    providers = payload["providers"]
    assert [p["provider"] for p in providers] == ["usajobs", "secondprovider"]
    assert providers[0]["state"] == "authorization_required"
    assert providers[1]["state"] == "configured"
    serialized = str(payload)
    assert "should-never-be-exposed" not in serialized
    assert "api_key" not in serialized


def test_capabilities_endpoint_defaults_country_to_us():
    client = api_service.app.test_client()
    response = client.get("/api/worker/live-jobs/capabilities")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["country_code"] == "US"
    assert payload["capability"] == "live_job_openings"
