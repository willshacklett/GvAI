"""Versioned, self-reported Worker Profile facts without scoring behavior."""

from __future__ import annotations

import re
from typing import Any, Dict, List


PROFILE_VERSION = "v1"
OCCUPATION_CODE_PATTERN = re.compile(r"^\d{2}-\d{4}(?:\.\d{2})?$")


class WorkerProfileValidationError(ValueError):
    """Validation error that exposes field names but never submitted values."""

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        super().__init__("Invalid Worker Profile.")


def _mapping(value: Any, field: str, errors: List[str]) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append(field)
        return {}
    return value


def _text(value: Any, field: str, maximum: int, errors: List[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append(field)
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        errors.append(field)
        return None
    return normalized


def _number(
    value: Any, field: str, minimum: float, maximum: float, errors: List[str]
) -> float | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(field)
        return None
    if value < minimum or value > maximum:
        errors.append(field)
        return None
    return value


def _boolean(value: Any, field: str, errors: List[str]) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        errors.append(field)
        return None
    return value


def _list(value: Any, field: str, errors: List[str]) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 50:
        errors.append(field)
        return []
    normalized = []
    seen = set()
    for item in value:
        text = _text(item, field, 120, errors)
        if text is None:
            continue
        key = text.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(text)
    return normalized


def validate_worker_profile(payload: Any) -> Dict[str, Any]:
    """Validate and normalize a self-reported Worker Profile V1 payload."""
    errors: List[str] = []
    if not isinstance(payload, dict):
        raise WorkerProfileValidationError(["profile"])

    if payload.get("profile_version") != PROFILE_VERSION:
        errors.append("profile_version")

    current_occupation = _mapping(payload.get("current_occupation"), "current_occupation", errors)
    occupation_code = _text(current_occupation.get("occupation_code"), "current_occupation.occupation_code", 10, errors)
    if occupation_code is not None:
        occupation_code = occupation_code.upper()
        if not OCCUPATION_CODE_PATTERN.fullmatch(occupation_code):
            errors.append("current_occupation.occupation_code")
    occupation_title = _text(current_occupation.get("occupation_title"), "current_occupation.occupation_title", 160, errors)

    experience = _mapping(payload.get("experience"), "experience", errors)
    education = _mapping(payload.get("education"), "education", errors)
    wage = _mapping(payload.get("wage"), "wage", errors)
    mobility = _mapping(payload.get("mobility"), "mobility", errors)
    preferences = _mapping(payload.get("preferences"), "preferences", errors)
    remote_preference = _text(mobility.get("remote_preference"), "mobility.remote_preference", 30, errors)
    if remote_preference not in (None, "no_preference", "prefer_remote", "remote_required", "prefer_on_site"):
        errors.append("mobility.remote_preference")

    profile = {
        "profile_version": PROFILE_VERSION,
        "claim_source": "self_reported",
        "current_occupation": {
            "occupation_code": occupation_code,
            "occupation_title": occupation_title,
        },
        "experience": {
            "years_in_current_occupation": _number(experience.get("years_in_current_occupation"), "experience.years_in_current_occupation", 0, 80, errors),
            "total_years_work_experience": _number(experience.get("total_years_work_experience"), "experience.total_years_work_experience", 0, 80, errors),
        },
        "education": {
            "highest_level": _text(education.get("highest_level"), "education.highest_level", 160, errors),
            "field_of_study": _text(education.get("field_of_study"), "education.field_of_study", 160, errors),
        },
        "credentials": _list(payload.get("credentials"), "credentials", errors),
        "skills": _list(payload.get("skills"), "skills", errors),
        "wage": {
            "current_hourly": _number(wage.get("current_hourly"), "wage.current_hourly", 0, 1000, errors),
            "current_annual": _number(wage.get("current_annual"), "wage.current_annual", 0, 2000000, errors),
            "minimum_hourly": _number(wage.get("minimum_hourly"), "wage.minimum_hourly", 0, 1000, errors),
            "minimum_annual": _number(wage.get("minimum_annual"), "wage.minimum_annual", 0, 2000000, errors),
        },
        "mobility": {
            "radius_miles": _number(mobility.get("radius_miles"), "mobility.radius_miles", 0, 1000, errors),
            "willing_to_relocate": _boolean(mobility.get("willing_to_relocate"), "mobility.willing_to_relocate", errors),
            "remote_preference": remote_preference,
        },
        "preferences": {
            "notes": _text(preferences.get("notes"), "preferences.notes", 1000, errors),
        },
    }
    if errors:
        raise WorkerProfileValidationError(sorted(set(errors)))
    return profile


normalize_worker_profile = validate_worker_profile