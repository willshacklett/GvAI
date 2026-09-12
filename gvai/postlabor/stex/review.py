from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .aggregate import aggregate_occupation_stex
from .records import STEX_REVIEW_STATUSES, TaskRatingRecord
from .store import (
    DEFAULT_STEX_DATA_ROOT,
    DEFAULT_STEX_TASK_RATINGS_ROOT,
    load_occupation_stex_profile,
    load_occupation_stex_tasks,
    list_occupation_stex_profiles,
    normalize_occupation_code,
    occupation_profile_path,
)


class STEXReviewError(ValueError):
    pass


def list_proposed_occupations(
    data_root: Path | None = None,
) -> list[dict[str, Any]]:
    return list_occupation_stex_profiles(
        data_root=data_root,
        review_status="proposed",
    )


def _task_record_from_payload(payload: dict[str, Any]) -> TaskRatingRecord:
    required = {
        "schema_version",
        "rubric_version",
        "occupation_code",
        "occupation_title",
        "task_id",
        "task_title",
        "task_category",
        "source_importance",
        "importance_status",
        "source_name",
        "source_year",
        "source_vintage_label",
        "digital_capability",
        "physical_execution",
        "human_presence_requirement",
        "augmentation_likelihood",
        "structural_exposure",
        "scorer_id",
        "scored_at_utc",
        "rationale",
        "review_status",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise STEXReviewError(
            "Task rating is missing required fields: " + ", ".join(missing)
        )
    if payload["review_status"] not in STEX_REVIEW_STATUSES:
        raise STEXReviewError("Task rating has an invalid review_status.")

    try:
        record = TaskRatingRecord.create(
            occupation_code=payload["occupation_code"],
            occupation_title=payload["occupation_title"],
            task_id=payload["task_id"],
            task_title=payload["task_title"],
            task_category=payload["task_category"],
            source_importance=payload["source_importance"],
            source_name=payload["source_name"],
            source_year=payload["source_year"],
            digital_capability=payload["digital_capability"],
            physical_execution=payload["physical_execution"],
            human_presence_requirement=payload["human_presence_requirement"],
            augmentation_likelihood=payload["augmentation_likelihood"],
            scorer_id=payload["scorer_id"],
            rationale=payload["rationale"],
            scored_at_utc=payload["scored_at_utc"],
            review_status=payload["review_status"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise STEXReviewError(f"Invalid task rating schema: {exc}") from exc

    if payload["schema_version"] != record.schema_version:
        raise STEXReviewError("Task rating schema_version is invalid.")
    if payload["rubric_version"] != record.rubric_version:
        raise STEXReviewError("Task rating rubric_version is invalid.")
    if payload["source_vintage_label"] != record.source_vintage_label:
        raise STEXReviewError("Task rating source vintage is inconsistent.")
    if payload["importance_status"] != record.importance_status:
        raise STEXReviewError("Task rating importance status is inconsistent.")
    if float(payload["structural_exposure"]) != record.structural_exposure:
        raise STEXReviewError("Task rating exposure does not match D/P/R.")
    return record


def get_review_package(
    occupation_code: str,
    *,
    data_root: Path | None = None,
    ratings_root: Path | None = None,
) -> dict[str, Any]:
    code = normalize_occupation_code(occupation_code)
    profile = load_occupation_stex_profile(code, data_root=data_root)
    tasks = load_occupation_stex_tasks(code, data_root=ratings_root)
    if profile.get("review_status") != "proposed":
        raise STEXReviewError("Only proposed occupations can enter review.")

    package_tasks = []
    for task in tasks:
        package_tasks.append({
            "task_id": task["task_id"],
            "task_statement": task["task_title"],
            "source_importance": task["source_importance"],
            "importance_status": task["importance_status"],
            "digital_capability": task["digital_capability"],
            "physical_execution": task["physical_execution"],
            "human_presence_requirement": task["human_presence_requirement"],
            "structural_exposure": task["structural_exposure"],
            "augmentation_likelihood": task["augmentation_likelihood"],
            "rationale": task["rationale"],
            "review_status": task["review_status"],
            "source_name": task["source_name"],
            "source_year": task["source_year"],
            "rubric_version": task["rubric_version"],
        })

    return {
        "occupation_code": profile["occupation_code"],
        "occupation_title": profile["occupation_title"],
        "review_status": profile["review_status"],
        "rubric_version": profile["rubric_version"],
        "structural_exposure": profile["structural_exposure"],
        "augmentation_likelihood": profile["augmentation_likelihood"],
        "rated_task_count": profile["rated_task_count"],
        "unrated_task_count": profile["unrated_task_count"],
        "source": profile.get("source"),
        "tasks": package_tasks,
    }


def _validate_approval(
    code: str,
    *,
    data_root: Path,
    ratings_root: Path,
) -> tuple[dict[str, Any], list[TaskRatingRecord]]:
    profile = load_occupation_stex_profile(code, data_root=data_root)
    if profile.get("review_status") != "proposed":
        raise STEXReviewError("Occupation is not currently proposed.")

    task_dir = ratings_root / code.replace(".", "_")
    if not task_dir.is_dir():
        raise STEXReviewError("No task ratings exist for the occupation.")
    raw_tasks = []
    for path in sorted(task_dir.glob("*.json")):
        try:
            task = json.loads(path.read_text())
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise STEXReviewError(
                f"Task rating file is unreadable: {path.name}"
            ) from exc
        if task.get("occupation_code") != code:
            raise STEXReviewError("Task occupation does not match profile.")
        raw_tasks.append(task)
    if not raw_tasks:
        raise STEXReviewError("No task ratings exist for the occupation.")
    records = []
    for task in raw_tasks:
        if task.get("occupation_code") != code:
            raise STEXReviewError("Task occupation does not match profile.")
        if task.get("review_status") != "proposed":
            raise STEXReviewError("All task ratings must be proposed.")
        record = _task_record_from_payload(task)
        if record.occupation_code != code:
            raise STEXReviewError("Task occupation does not match profile.")
        records.append(record)

    result = aggregate_occupation_stex(records)
    expected = {
        "occupation_code": result.occupation_code,
        "occupation_title": result.occupation_title,
        "rated_task_count": result.rated_task_count,
        "unrated_task_count": result.unrated_task_count,
        "total_importance_weight": result.total_importance_weight,
        "structural_exposure": result.structural_exposure,
        "augmentation_likelihood": result.augmentation_likelihood,
        "rubric_version": result.rubric_version,
    }
    for field, value in expected.items():
        if profile.get(field) != value:
            raise STEXReviewError(
                f"Occupation summary does not match task aggregation: {field}"
            )
    return profile, records


def _write_json_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _restore_bytes_atomically(path: Path, original: bytes) -> None:
    """Restore a pre-approval file without exposing a partial write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.rollback.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(original)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _normalize_review_timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if not isinstance(value, str) or not value.strip():
        raise STEXReviewError(
            "reviewed_at_utc must be a timezone-aware ISO-8601 timestamp."
        )
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise STEXReviewError(
            "reviewed_at_utc must be a timezone-aware ISO-8601 timestamp."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise STEXReviewError(
            "reviewed_at_utc must include a timezone offset."
        )
    return parsed.isoformat()


def approve_occupation(
    occupation_code: str,
    reviewed_by: str,
    review_note: str | None = None,
    *,
    data_root: Path | None = None,
    ratings_root: Path | None = None,
    reviewed_at_utc: str | None = None,
) -> dict[str, Any]:
    reviewer = (reviewed_by or "").strip()
    if not reviewer:
        raise STEXReviewError("reviewed_by must be a non-empty human identifier.")
    code = normalize_occupation_code(occupation_code)
    profile_root = Path(data_root) if data_root is not None else DEFAULT_STEX_DATA_ROOT
    ratings_base = Path(ratings_root) if ratings_root is not None else DEFAULT_STEX_TASK_RATINGS_ROOT
    profile, records = _validate_approval(
        code,
        data_root=profile_root,
        ratings_root=ratings_base,
    )
    timestamp = _normalize_review_timestamp(reviewed_at_utc)
    profile_path = occupation_profile_path(code, data_root=profile_root)
    task_paths = [ratings_base / code.replace(".", "_") / f"{record.task_id}.json" for record in records]
    original = {path: path.read_bytes() for path in [profile_path, *task_paths]}

    updated_tasks = []
    for record, path in zip(records, task_paths):
        payload = json.loads(path.read_text())
        payload.update({
            "review_status": "approved",
            "reviewed_at_utc": timestamp,
            "reviewed_by": reviewer,
        })
        if review_note is not None:
            payload["review_note"] = review_note
        updated_tasks.append((path, payload))

    updated_profile = dict(profile)
    updated_profile.update({
        "review_status": "approved",
        "reviewed_at_utc": timestamp,
        "reviewed_by": reviewer,
    })
    if review_note is not None:
        updated_profile["review_note"] = review_note

    replaced: list[Path] = []
    try:
        for path, payload in updated_tasks:
            _write_json_atomically(path, payload)
            replaced.append(path)
        _write_json_atomically(profile_path, updated_profile)
        replaced.append(profile_path)
    except Exception:
        for path in replaced:
            _restore_bytes_atomically(path, original[path])
        raise

    return updated_profile