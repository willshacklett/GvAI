from __future__ import annotations

from gvai.postlabor.sources.onet import OnetClient


def _client_with_payload(monkeypatch, payload):
    client = OnetClient(api_key="test-key")
    monkeypatch.setattr(client, "_get", lambda path, params=None: payload)
    return client


def test_work_activities_real_zero_importance_is_preserved(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "element": [
                {"id": "4.A.1.a.1", "name": "Getting Information", "description": "d", "importance": 0},
            ]
        },
    )
    result = client.work_activities("37-2021.00")
    assert result[0].importance == 0.0


def test_work_activities_missing_importance_is_none_not_zero(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "element": [
                {"id": "4.A.1.a.1", "name": "Getting Information", "description": "d"},
            ]
        },
    )
    result = client.work_activities("37-2021.00")
    assert result[0].importance is None


def test_skills_real_zero_importance_is_preserved(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "element": [
                {"id": "2.A.1.a", "name": "Reading Comprehension", "description": "d", "importance": 0},
            ]
        },
    )
    result = client.skills("37-2021.00")
    assert result[0].importance == 0.0


def test_skills_missing_importance_is_none_not_zero(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "element": [
                {"id": "2.A.1.a", "name": "Reading Comprehension", "description": "d", "importance": None},
            ]
        },
    )
    result = client.skills("37-2021.00")
    assert result[0].importance is None


def test_knowledge_real_zero_importance_is_preserved(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "element": [
                {"id": "2.C.1.a", "name": "Biology", "description": "d", "importance": 0},
            ]
        },
    )
    result = client.knowledge("37-2021.00")
    assert result[0].importance == 0.0


def test_knowledge_missing_importance_is_none_not_zero(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "element": [
                {"id": "2.C.1.a", "name": "Biology", "description": "d"},
            ]
        },
    )
    result = client.knowledge("37-2021.00")
    assert result[0].importance is None


def test_abilities_real_zero_importance_is_preserved(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "element": [
                {"id": "1.A.1.a.1", "name": "Oral Comprehension", "description": "d", "importance": 0},
            ]
        },
    )
    result = client.abilities("37-2021.00")
    assert result[0].importance == 0.0


def test_abilities_missing_importance_is_none_not_zero(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "element": [
                {"id": "1.A.1.a.1", "name": "Oral Comprehension", "description": "d", "importance": None},
            ]
        },
    )
    result = client.abilities("37-2021.00")
    assert result[0].importance is None


def test_job_zone_missing_text_fields_are_none_not_empty_string(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "code": 2,
            "title": "Job Zone 1-2",
            "education": None,
            "related_experience": None,
            "job_training": None,
            "job_zone_examples": None,
            "svp_range": None,
        },
    )
    result = client.job_zone("37-2021.00")
    assert result.code == 2
    assert result.title == "Job Zone 1-2"
    assert result.education is None
    assert result.related_experience is None
    assert result.job_training is None
    assert result.job_zone_examples is None
    assert result.svp_range is None


def test_job_zone_missing_key_entirely_is_none_not_empty_string(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {"code": 2, "title": "Job Zone 1-2"},
    )
    result = client.job_zone("37-2021.00")
    assert result.education is None
    assert result.related_experience is None


def test_job_zone_real_empty_string_field_is_preserved_as_empty_string(monkeypatch):
    """An upstream field that is actually '' (present, not null) is not
    the same as a missing field, and must not be conflated with None."""
    client = _client_with_payload(
        monkeypatch,
        {
            "code": 2,
            "title": "Job Zone 1-2",
            "education": "",
        },
    )
    result = client.job_zone("37-2021.00")
    assert result.education == ""


def test_education_zero_percentage_is_preserved(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "response": [
                {
                    "code": 2,
                    "title": "High school diploma or equivalent",
                    "percentage_of_respondents": 0,
                },
            ]
        },
    )
    result = client.education("37-2021.00")
    assert result[0].percentage_of_respondents == 0.0


def test_education_missing_percentage_is_none_not_zero(monkeypatch):
    client = _client_with_payload(
        monkeypatch,
        {
            "response": [
                {
                    "code": 2,
                    "title": "High school diploma or equivalent",
                },
            ]
        },
    )
    result = client.education("37-2021.00")
    assert result[0].percentage_of_respondents is None
