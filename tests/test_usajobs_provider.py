from gvai.postlabor.live_jobs import LiveJobsRegistry, PublicJobSearchContext
from gvai.postlabor.labor_providers import OccupationReference
from gvai.postlabor.usajobs_provider import USAJobsProvider


class FakeResponse:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


def _record(job_id="42"):
    return {
        "MatchedObjectDescriptor": {
            "PositionID": job_id,
            "PositionTitle": "Warehouse Worker",
            "PositionURI": f"https://www.usajobs.gov/job/{job_id}",
            "OrganizationName": "Public Employer",
            "PositionLocationDisplay": "Nashville, TN",
            "TeleworkEligible": "Yes",
            "PositionSchedule": [{"Name": "Full-time"}],
            "PositionRemuneration": [{
                "MinimumRange": "20",
                "MaximumRange": "24",
                "RateIntervalCode": "HOUR",
                "CurrencyCode": "USD",
            }],
            "PublicationStartDate": "2026-09-19",
        }
    }


def test_configured_provider_uses_title_as_search_query_and_preserves_provenance():
    session = FakeSession(FakeResponse({"SearchResult": {"SearchResultItems": [_record()]}}))
    provider = USAJobsProvider(
        api_key="configured", user_agent="ops@example.org", session=session
    )
    occupation = OccupationReference(
        "US", "usajobs", "text-search", "Warehouse Worker", mapping_type="search_query"
    )
    result = LiveJobsRegistry([provider]).search(
        PublicJobSearchContext("US", location="Nashville"), occupation=occupation
    )

    assert result.status == "available_with_results"
    opening = result.openings[0].to_dict()
    assert opening["provider_job_id"] == "42"
    assert opening["apply_url"] == "https://www.usajobs.gov/job/42"
    assert opening["source_attribution"] == "USAJOBS API"
    assert opening["compensation"]["minimum_amount"] == 20.0
    assert opening["compensation"]["currency"] == "USD"
    request = session.calls[0][1]
    assert request["params"]["Keyword"] == "Warehouse Worker"
    assert request["params"]["LocationName"] == "Nashville"
    assert "worker_profile" not in request["params"]


def test_supported_filters_are_translated_to_documented_usajobs_parameters():
    session = FakeSession(FakeResponse({"SearchResult": {"SearchResultItems": []}}))
    provider = USAJobsProvider(
        api_key="configured", user_agent="ops@example.org", session=session
    )
    provider.list_openings(
        country_code="US",
        location="37201",
        radius=25,
        remote_only=True,
        schedule_type_code="1",
        posted_within_days=7,
    )

    params = session.calls[0][1]["params"]
    assert params == {
        "ResultsPerPage": 25,
        "LocationName": "37201",
        "Radius": 25,
        "RemoteIndicator": "True",
        "PositionScheduleTypeCode": "1",
        "DatePosted": 7,
    }


def test_missing_optional_fields_remain_unknown():
    record = _record()
    descriptor = record["MatchedObjectDescriptor"]
    for field in (
        "OrganizationName",
        "PositionLocationDisplay",
        "TeleworkEligible",
        "PositionSchedule",
        "PositionRemuneration",
        "PublicationStartDate",
    ):
        descriptor.pop(field)
    session = FakeSession(FakeResponse({"SearchResult": {"SearchResultItems": [record]}}))
    provider = USAJobsProvider(
        api_key="configured", user_agent="ops@example.org", session=session
    )

    opening = LiveJobsRegistry([provider]).search(PublicJobSearchContext("US")).openings[0]
    assert opening.employer is None
    assert opening.location is None
    assert opening.employment_type is None
    assert opening.compensation is None
    assert opening.remote_or_hybrid is None
    assert opening.posted_at is None


def test_published_compensation_telework_and_posting_date_are_preserved():
    session = FakeSession(FakeResponse({"SearchResult": {"SearchResultItems": [_record()]}}))
    provider = USAJobsProvider(
        api_key="configured", user_agent="ops@example.org", session=session
    )
    opening = LiveJobsRegistry([provider]).search(PublicJobSearchContext("US")).openings[0]

    assert opening.compensation.minimum_amount == 20.0
    assert opening.compensation.maximum_amount == 24.0
    assert opening.compensation.interval == "hour"
    assert opening.remote_or_hybrid == "Yes"
    assert opening.posted_at.isoformat() == "2026-09-19T00:00:00+00:00"


def test_missing_configuration_is_detected_without_a_network_call():
    session = FakeSession(FakeResponse({}))
    provider = USAJobsProvider(session=session)
    assert provider.configured is False
    result = LiveJobsRegistry([provider]).search(PublicJobSearchContext("US"))
    assert result.status == "provider_unavailable"
    assert session.calls == []


def test_duplicates_and_malformed_records_are_isolated_and_result_limit_applies():
    records = [_record("1"), _record("1"), {"malformed": True}]
    session = FakeSession(FakeResponse({"SearchResult": {"SearchResultItems": records}}))
    provider = USAJobsProvider(
        api_key="configured", user_agent="ops@example.org", session=session, result_limit=1
    )
    result = LiveJobsRegistry([provider]).search(PublicJobSearchContext("US"))
    assert result.status == "available_with_results"
    assert [opening.provider_job_id for opening in result.openings] == ["1"]


def test_upstream_failure_is_explicit_and_country_isolation_is_preserved():
    session = FakeSession(None)
    session.response = FakeResponse(error=RuntimeError("upstream unavailable"))
    provider = USAJobsProvider(
        api_key="configured", user_agent="ops@example.org", session=session
    )
    result = LiveJobsRegistry([provider]).search(PublicJobSearchContext("US"))
    assert result.status == "provider_failure"
    assert LiveJobsRegistry([provider]).search(PublicJobSearchContext("CA")).status == "unsupported_country"