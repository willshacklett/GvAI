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
class OnetWorkActivity:
    element_id: str
    name: str
    description: str
    importance: float


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
    importance: float



ONET_BASE_URL = "https://api-v2.onetcenter.org"


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
                importance=float(item.get("importance") or 0.0),
            )
            for item in elements
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
                importance=float(item.get("importance") or 0.0),
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
