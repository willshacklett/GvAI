from __future__ import annotations

import os
from typing import List, Optional

import requests

from gvai.postlabor.workers.occupation_data import (
    OccupationRecord,
    OccupationSkill,
)


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

        if not self.api_key:
            raise RuntimeError(
                "O*NET API key missing. Set ONET_API_KEY in the environment."
            )

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        response = requests.get(
            f"{ONET_BASE_URL}{path}",
            headers={
                "X-API-Key": self.api_key,
                "Accept": "application/json",
            },
            params=params or {},
            timeout=self.timeout,
        )

        response.raise_for_status()
        return response.json()

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
