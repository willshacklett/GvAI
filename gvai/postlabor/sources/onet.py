from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import requests

from gvai.postlabor.workers.occupation_data import (
    OccupationRecord,
    OccupationSkill,
)


@dataclass(frozen=True)
class OnetTask:
    task_id: str
    title: str
    importance: float
    category: str


@dataclass(frozen=True)
class OnetWorkActivity:
    element_id: str
    name: str
    description: str
    importance: Optional[float]


@dataclass(frozen=True)
class OnetWorkContext:
    element_id: str
    name: str
    description: str
    context: float



@dataclass(frozen=True)
class OnetKnowledge:
    element_id: str
    name: str
    description: str
    importance: Optional[float]



@dataclass(frozen=True)
class OnetAbility:
    element_id: str
    name: str
    description: str
    importance: Optional[float]



@dataclass(frozen=True)
class OnetJobZone:
    code: Optional[int]
    title: Optional[str]
    education: Optional[str]
    related_experience: Optional[str]
    job_training: Optional[str]
    job_zone_examples: Optional[str]
    svp_range: Optional[str]



@dataclass(frozen=True)
class OnetEducationLevel:
    code: Optional[int]
    title: str
    percentage_of_respondents: Optional[float]



@dataclass(frozen=True)
class OnetRelatedOccupation:
    occupation_code: str
    title: str
    bright_outlook: bool = False



ONET_BASE_URL = "https://api-v2.onetcenter.org"


def _optional_str(value: object) -> Optional[str]:
    """Preserve a missing/null upstream field as None, never as ''."""
    return None if value is None else str(value)


def _optional_float(value: object) -> Optional[float]:
    """Preserve a missing/null upstream number as None, never as 0.0."""
    return None if value is None else float(value)


class OnetClient:
    """
    Minimal O*NET Web Services v2 client.

    Requires ONET_API_KEY in the environment.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key or os.getenv("ONET_API_KEY")
        self.timeout = timeout
        self._response_cache = {}

        if not self.api_key:
            raise RuntimeError(
                "O*NET API key missing. Set ONET_API_KEY in the environment."
            )

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        params = params or {}

        cache_key = (
            path,
            tuple(sorted(params.items())),
        )

        cached = self._response_cache.get(cache_key)
        if cached is not None:
            return cached

        response = requests.get(
            f"{ONET_BASE_URL}{path}",
            headers={
                "X-API-Key": self.api_key,
                "Accept": "application/json",
            },
            params=params,
            timeout=self.timeout,
        )

        response.raise_for_status()
        payload = response.json()

        self._response_cache[cache_key] = payload

        return payload

    def occupation(self, occupation_code: str) -> OccupationRecord:
        payload = self._get(
            f"/online/occupations/{occupation_code}/"
        )

        tags = payload.get("tags") or {}

        return OccupationRecord(
            occupation_code=str(payload.get("code") or occupation_code),
            title=str(payload.get("title") or ""),
            description=str(payload.get("description") or ""),
            bright_outlook=tags.get("bright_outlook"),
            skills=[],
        )

    def skills(
        self,
        occupation_code: str,
        *,
        start: int = 1,
        end: int = 100,
    ) -> List[OccupationSkill]:
        payload = self._get(
            f"/online/occupations/{occupation_code}/details/skills",
            params={
                "start": start,
                "end": end,
                "sort": "importance",
            },
        )

        elements = payload.get("element") or []

        return [
            OccupationSkill(
                skill_id=str(item.get("id") or ""),
                name=str(item.get("name") or ""),
                importance=(
                    float(item["importance"])
                    if item.get("importance") is not None
                    else None
                ),
                description=str(item.get("description") or ""),
            )
            for item in elements
        ]

    def related_occupations(
        self,
        occupation_code: str,
        *,
        start: int = 1,
        end: int = 50,
    ) -> List[OnetRelatedOccupation]:
        payload = self._get(
            f"/online/occupations/{occupation_code}/details/related_occupations",
            params={
                "start": start,
                "end": end,
            },
        )

        occupations = payload.get("occupation") or []

        return [
            OnetRelatedOccupation(
                occupation_code=str(item.get("code") or ""),
                title=str(item.get("title") or ""),
                bright_outlook=bool(
                    (item.get("tags") or {}).get("bright_outlook", False)
                ),
            )
            for item in occupations
        ]

    def knowledge(
        self,
        occupation_code: str,
    ) -> List[OnetKnowledge]:
        payload = self._get(
            f"/online/occupations/{occupation_code}/details/knowledge",
            params={
                "start": 1,
                "end": 100,
                "sort": "importance",
            },
        )

        elements = payload.get("element") or []

        return [
            OnetKnowledge(
                element_id=str(item.get("id") or ""),
                name=str(item.get("name") or ""),
                description=str(item.get("description") or ""),
                importance=_optional_float(item.get("importance")),
            )
            for item in elements
        ]

    def abilities(
        self,
        occupation_code: str,
    ) -> List[OnetAbility]:
        payload = self._get(
            f"/online/occupations/{occupation_code}/details/abilities",
            params={
                "start": 1,
                "end": 100,
                "sort": "importance",
            },
        )

        elements = payload.get("element") or []

        return [
            OnetAbility(
                element_id=str(item.get("id") or ""),
                name=str(item.get("name") or ""),
                description=str(item.get("description") or ""),
                importance=_optional_float(item.get("importance")),
            )
            for item in elements
        ]

    def job_zone(
        self,
        occupation_code: str,
    ) -> OnetJobZone:
        payload = self._get(
            f"/online/occupations/{occupation_code}/details/job_zone",
        )

        return OnetJobZone(
            code=(
                int(payload["code"])
                if payload.get("code") is not None
                else None
            ),
            title=_optional_str(payload.get("title")),
            education=_optional_str(payload.get("education")),
            related_experience=_optional_str(payload.get("related_experience")),
            job_training=_optional_str(payload.get("job_training")),
            job_zone_examples=_optional_str(payload.get("job_zone_examples")),
            svp_range=_optional_str(payload.get("svp_range")),
        )

    def education(
        self,
        occupation_code: str,
    ) -> List[OnetEducationLevel]:
        payload = self._get(
            f"/online/occupations/{occupation_code}/details/education",
        )

        levels = payload.get("response") or []

        return [
            OnetEducationLevel(
                code=(
                    int(item["code"])
                    if item.get("code") is not None
                    else None
                ),
                title=str(item.get("title") or ""),
                percentage_of_respondents=(
                    float(item["percentage_of_respondents"])
                    if item.get("percentage_of_respondents") is not None
                    else None
                ),
            )
            for item in levels
        ]

    def tasks(
        self,
        occupation_code: str,
        *,
        start: int = 1,
        end: int = 100,
    ) -> List[OnetTask]:
        payload = self._get(
            f"/online/occupations/{occupation_code}/details/tasks",
            params={
                "start": start,
                "end": end,
            },
        )

        tasks = payload.get("task") or []

        return [
            OnetTask(
                task_id=str(item.get("id") or ""),
                title=str(item.get("title") or ""),
                importance=float(item.get("importance") or 0.0),
                category=str(item.get("category") or ""),
            )
            for item in tasks
        ]

    def work_activities(
        self,
        occupation_code: str,
    ) -> List[OnetWorkActivity]:
        payload = self._get(
            f"/online/occupations/{occupation_code}/details/work_activities",
            params={
                "start": 1,
                "end": 100,
                "sort": "importance",
            },
        )

        elements = payload.get("element") or []

        return [
            OnetWorkActivity(
                element_id=str(item.get("id") or ""),
                name=str(item.get("name") or ""),
                description=str(item.get("description") or ""),
                importance=_optional_float(item.get("importance")),
            )
            for item in elements
        ]

    def work_context(
        self,
        occupation_code: str,
    ) -> List[OnetWorkContext]:
        payload = self._get(
            f"/online/occupations/{occupation_code}/details/work_context",
            params={
                "start": 1,
                "end": 100,
            },
        )

        elements = payload.get("element") or []

        return [
            OnetWorkContext(
                element_id=str(item.get("id") or ""),
                name=str(item.get("name") or ""),
                description=str(item.get("description") or ""),
                context=float(item.get("context") or 0.0),
            )
            for item in elements
        ]

    def occupation_with_skills(
        self,
        occupation_code: str,
    ) -> OccupationRecord:
        occupation = self.occupation(occupation_code)
        skills = self.skills(occupation_code)

        return OccupationRecord(
            occupation_code=occupation.occupation_code,
            title=occupation.title,
            description=occupation.description,
            bright_outlook=occupation.bright_outlook,
            skills=skills,
        )
