import json
import shutil
from pathlib import Path

import pytest

import gvai.api_service as api_service
import gvai.postlabor.stex.review as review_module
from gvai.postlabor.stex.review import (
    STEXReviewError,
    approve_occupation,
    get_review_package,
    list_proposed_occupations,
)
from gvai.postlabor.stex.store import list_occupation_stex_profiles


ROOT = Path(__file__).resolve().parents[2]
CODE = "53-7062.00"
SAFE = CODE.replace(".", "_")


def make_fixture(tmp_path):
    data_root = tmp_path / "occupations"
    ratings_root = tmp_path / "ratings"
    data_root.mkdir()
    shutil.copy(
        ROOT / "data" / "stex" / "occupations" / f"{SAFE}.stex.json",
        data_root / f"{SAFE}.stex.json",
    )
    shutil.copytree(
        ROOT / "data" / "stex" / "ratings" / SAFE,
        ratings_root / SAFE,
    )
    return data_root, ratings_root


def read_profile(data_root):
    return json.loads((data_root / f"{SAFE}.stex.json").read_text())


def read_task(ratings_root, task_id="10789"):
    return json.loads((ratings_root / SAFE / f"{task_id}.json").read_text())


def write_profile(data_root, payload):
    (data_root / f"{SAFE}.stex.json").write_text(json.dumps(payload, indent=2) + "\n")


def fixture_revision(data_root, ratings_root):
    return get_review_package(
        CODE,
        data_root=data_root,
        ratings_root=ratings_root,
    )["approval_revision"]


def test_real_review_queue_has_five_proposed_and_excludes_approved():
    proposed = {item["occupation_code"] for item in list_proposed_occupations()}
    approved = {item["occupation_code"] for item in list_occupation_stex_profiles()}

    assert proposed == {
        "53-7062.00",
        "35-3023.00",
        "41-2031.00",
        "29-1141.00",
        "11-1021.00",
    }
    assert approved == {"15-1252.00", "37-2021.00"}


def test_review_package_contains_source_and_all_tasks():
    package = get_review_package(CODE)

    assert package["review_status"] == "proposed"
    assert package["rubric_version"] == "STEX v0.2"
    assert package["source"]["tasks_year"] == 2024
    assert len(package["approval_revision"]) == 64
    assert len(package["tasks"]) == 14
    assert {
        "task_id",
        "task_statement",
        "source_importance",
        "importance_status",
        "digital_capability",
        "physical_execution",
        "human_presence_requirement",
        "structural_exposure",
        "augmentation_likelihood",
        "rationale",
        "review_status",
    } <= package["tasks"][0].keys()


def test_approval_requires_non_empty_reviewer(tmp_path):
    data_root, ratings_root = make_fixture(tmp_path)

    with pytest.raises(STEXReviewError, match="reviewed_by"):
        approve_occupation(
            CODE,
            "   ",
            approval_revision=fixture_revision(data_root, ratings_root),
            data_root=data_root,
            ratings_root=ratings_root,
        )


@pytest.mark.parametrize("timestamp", ["not-a-timestamp", "2026-09-12T12:00:00"])
def test_invalid_review_timestamp_is_rejected_before_mutation(tmp_path, timestamp):
    data_root, ratings_root = make_fixture(tmp_path)
    before = {
        path: path.read_bytes()
        for path in [
            data_root / f"{SAFE}.stex.json",
            *(ratings_root / SAFE).glob("*.json"),
        ]
    }

    with pytest.raises(STEXReviewError):
        approve_occupation(
            CODE,
            "Will Shacklett",
            approval_revision=fixture_revision(data_root, ratings_root),
            data_root=data_root,
            ratings_root=ratings_root,
            reviewed_at_utc=timestamp,
        )

    assert {path: path.read_bytes() for path in before} == before


def test_valid_timezone_aware_review_timestamp_is_normalized(tmp_path):
    data_root, ratings_root = make_fixture(tmp_path)

    result = approve_occupation(
        CODE,
        "Will Shacklett",
        approval_revision=fixture_revision(data_root, ratings_root),
        data_root=data_root,
        ratings_root=ratings_root,
        reviewed_at_utc="2026-09-12T08:00:00-04:00",
    )

    assert result["reviewed_at_utc"] == "2026-09-12T08:00:00-04:00"


@pytest.mark.parametrize("mutation, expected_task_status", [
    (lambda profile, task: profile.update({"structural_exposure": 99.0}), "proposed"),
    (lambda profile, task: task.update({"occupation_code": "11-1021.00"}), "proposed"),
    (lambda profile, task: task.update({"review_status": "approved"}), "approved"),
    (lambda profile, task: task.update({"structural_exposure": 99.0}), "proposed"),
])
def test_failed_approval_leaves_fixture_unchanged(tmp_path, mutation, expected_task_status):
    data_root, ratings_root = make_fixture(tmp_path)
    profile = read_profile(data_root)
    task = read_task(ratings_root)
    mutation(profile, task)
    write_profile(data_root, profile)
    (ratings_root / SAFE / "10789.json").write_text(json.dumps(task, indent=2) + "\n")

    with pytest.raises(STEXReviewError):
        approve_occupation(
            CODE,
            "Will Shacklett",
            approval_revision=fixture_revision(data_root, ratings_root),
            data_root=data_root,
            ratings_root=ratings_root,
        )

    assert read_profile(data_root)["review_status"] == "proposed"
    assert json.loads((ratings_root / SAFE / "10789.json").read_text())["review_status"] == expected_task_status


def test_successful_approval_updates_profile_and_every_task(tmp_path):
    data_root, ratings_root = make_fixture(tmp_path)

    result = approve_occupation(
        CODE,
        "Will Shacklett",
        "Reviewed task-by-task against STEX v0.1 rubric.",
        fixture_revision(data_root, ratings_root),
        data_root=data_root,
        ratings_root=ratings_root,
        reviewed_at_utc="2026-09-12T12:00:00+00:00",
    )

    assert result["review_status"] == "approved"
    assert result["reviewed_by"] == "Will Shacklett"
    assert result["reviewed_at_utc"] == "2026-09-12T12:00:00+00:00"
    assert result["review_note"]
    assert list_proposed_occupations(data_root) == []
    assert list_occupation_stex_profiles(data_root=data_root) == [
        {**list_occupation_stex_profiles(data_root=data_root, review_status=None)[0],
         "review_status": "approved"}
    ]
    assert all(
        json.loads(path.read_text())["review_status"] == "approved"
        for path in (ratings_root / SAFE).glob("*.json")
    )


def test_approval_rejects_already_approved_profile(tmp_path):
    data_root, ratings_root = make_fixture(tmp_path)
    revision = fixture_revision(data_root, ratings_root)
    approve_occupation(CODE, "Will Shacklett", approval_revision=revision, data_root=data_root, ratings_root=ratings_root)

    with pytest.raises(STEXReviewError, match="not currently proposed"):
        approve_occupation(CODE, "Will Shacklett", approval_revision=revision, data_root=data_root, ratings_root=ratings_root)


def test_semantically_identical_json_formatting_keeps_revision(tmp_path):
    data_root, ratings_root = make_fixture(tmp_path)
    before = fixture_revision(data_root, ratings_root)
    profile_path = data_root / f"{SAFE}.stex.json"
    profile_path.write_text(json.dumps(json.loads(profile_path.read_text()), sort_keys=True, separators=(",", ":")))
    for path in (ratings_root / SAFE).glob("*.json"):
        path.write_text(json.dumps(json.loads(path.read_text()), sort_keys=True, indent=4) + "\n")

    assert fixture_revision(data_root, ratings_root) == before


def test_changed_task_after_review_makes_revision_stale(tmp_path):
    data_root, ratings_root = make_fixture(tmp_path)
    reviewed_revision = fixture_revision(data_root, ratings_root)
    task_path = ratings_root / SAFE / "10789.json"
    task = json.loads(task_path.read_text())
    task["rationale"] = task["rationale"] + " Changed after review."
    task_path.write_text(json.dumps(task, indent=2) + "\n")
    before = {
        path: path.read_bytes()
        for path in [data_root / f"{SAFE}.stex.json", *(ratings_root / SAFE).glob("*.json")]
    }

    with pytest.raises(STEXReviewError, match="stale"):
        approve_occupation(
            CODE,
            "Will Shacklett",
            approval_revision=reviewed_revision,
            data_root=data_root,
            ratings_root=ratings_root,
        )

    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize(
    "field, value",
    [
        ("reviewed_by", 42),
        ("review_note", {"not": "a string"}),
        ("approval_revision", "bad"),
    ],
)
def test_malformed_approval_fields_fail_without_writes(tmp_path, field, value):
    data_root, ratings_root = make_fixture(tmp_path)
    payload = {
        "reviewed_by": "Will Shacklett",
        "review_note": None,
        "approval_revision": fixture_revision(data_root, ratings_root),
    }
    payload[field] = value
    before = {
        path: path.read_bytes()
        for path in [data_root / f"{SAFE}.stex.json", *(ratings_root / SAFE).glob("*.json")]
    }

    with pytest.raises(STEXReviewError):
        approve_occupation(
            CODE,
            payload["reviewed_by"],
            payload["review_note"],
            payload["approval_revision"],
            data_root=data_root,
            ratings_root=ratings_root,
        )

    assert {path: path.read_bytes() for path in before} == before


def test_write_failure_rolls_back_all_replacements(tmp_path, monkeypatch):
    data_root, ratings_root = make_fixture(tmp_path)
    profile_path = data_root / f"{SAFE}.stex.json"
    task_paths = sorted((ratings_root / SAFE).glob("*.json"))
    paths = [*task_paths, profile_path]
    originals = {path: path.read_bytes() for path in paths}
    calls = 0
    restored = []
    real_writer = review_module._write_json_atomically
    real_restore = review_module._restore_bytes_atomically

    def fail_after_first(path, payload):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("simulated replacement failure")
        real_writer(path, payload)

    def track_restore(path, original):
        restored.append(path)
        real_restore(path, original)

    monkeypatch.setattr(review_module, "_write_json_atomically", fail_after_first)
    monkeypatch.setattr(review_module, "_restore_bytes_atomically", track_restore)
    with pytest.raises(OSError, match="simulated"):
        approve_occupation(CODE, "Will Shacklett", approval_revision=fixture_revision(data_root, ratings_root), data_root=data_root, ratings_root=ratings_root)

    assert {path: path.read_bytes() for path in paths} == originals
    assert restored == task_paths[:2]
    assert read_profile(data_root)["review_status"] == "proposed"


def test_build_script_has_no_approval_operation():
    source = (ROOT / "scripts" / "build_nashville_stex_ratings.py").read_text()

    assert 'review_status="proposed"' in source
    assert "approve_occupation" not in source


def test_api_write_gate_and_enabled_transition(monkeypatch, tmp_path):
    data_root, ratings_root = make_fixture(tmp_path)
    calls = []

    def fake_approve(code, reviewer, note, revision):
        calls.append((code, reviewer, note, revision))
        return approve_occupation(
            code,
            reviewer,
            note,
            revision,
            data_root=data_root,
            ratings_root=ratings_root,
            reviewed_at_utc="2026-09-12T12:00:00+00:00",
        )

    monkeypatch.delenv("GVAI_STEX_REVIEW_WRITES_ENABLED", raising=False)
    monkeypatch.setattr(api_service, "approve_occupation", fake_approve)
    client = api_service.app.test_client()
    payload = {
        "occupation_code": CODE,
        "reviewed_by": "Will Shacklett",
        "approval_revision": fixture_revision(data_root, ratings_root),
    }

    disabled = client.post("/api/stex/review/approve", json=payload)
    assert disabled.status_code == 403
    assert calls == []

    monkeypatch.setenv("GVAI_STEX_REVIEW_WRITES_ENABLED", "1")
    enabled = client.post("/api/stex/review/approve", json=payload)
    assert enabled.status_code == 200
    assert enabled.get_json()["profile"]["review_status"] == "approved"
    assert calls == [(CODE, "Will Shacklett", None, payload["approval_revision"])]


def test_api_enabled_missing_revision_returns_controlled_error(monkeypatch):
    monkeypatch.setenv("GVAI_STEX_REVIEW_WRITES_ENABLED", "1")
    client = api_service.app.test_client()

    response = client.post(
        "/api/stex/review/approve",
        json={"occupation_code": CODE, "reviewed_by": "Will Shacklett"},
    )

    assert response.status_code == 409
    assert "approval_revision" in response.get_json()["reason"]


def test_review_get_endpoints_are_read_only_and_local(monkeypatch):
    def fail_network(*args, **kwargs):
        raise AssertionError("review route attempted network access")

    monkeypatch.setattr("gvai.postlabor.sources.bls.requests.post", fail_network)
    monkeypatch.setattr("gvai.postlabor.sources.oews.requests.get", fail_network)
    client = api_service.app.test_client()

    queue = client.get("/api/stex/review/proposed")
    package = client.get("/api/stex/review/occupation?code=53-7062.00")

    assert queue.status_code == 200
    assert queue.get_json()["count"] == 5
    assert package.status_code == 200
    assert len(package.get_json()["package"]["tasks"]) == 14