"""Authorized USAJOBS live-openings adapter.

The adapter is opt-in: both USAJOBS_API_KEY and USAJOBS_USER_AGENT must be
configured. Occupation titles are sent as textual search queries, never as
authoritative occupation mappings.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import requests

from gvai.postlabor.labor_providers import (
    OccupationReference,
    ProviderMetadata,
)


USAJOBS_METADATA = ProviderMetadata(
    country_code="US",
    provider="usajobs",
    capabilities=frozenset({"live_job_openings"}),
    attribution="USAJOBS API",
)


class USAJobsProvider:
    metadata = USAJOBS_METADATA
    endpoint = "https://data.usajobs.gov/api/search"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        user_agent: str | None = None,
        timeout_seconds: float | None = None,
        result_limit: int | None = None,
        session: Any = requests,
    ) -> None:
        self.api_key = api_key or os.getenv("USAJOBS_API_KEY")
        self.user_agent = user_agent or os.getenv("USAJOBS_USER_AGENT")
        self.timeout_seconds = timeout_seconds or self._env_float("USAJOBS_TIMEOUT_SECONDS", 8.0)
        self.result_limit = result_limit or self._env_int("USAJOBS_RESULT_LIMIT", 25)
        self.session = session

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            return default

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.user_agent)

    def list_openings(
        self,
        *,
        occupation: OccupationReference | None = None,
        country_code: str | None = None,
        location: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius: float | None = None,
    ) -> Sequence[Mapping[str, object]]:
        if (country_code or "US").upper() != "US":
            raise ValueError("USAJOBS only supports US openings.")
        if not self.configured:
            raise RuntimeError("USAJOBS provider is not configured.")

        params: dict[str, object] = {"ResultsPerPage": max(1, min(self.result_limit, 100))}
        if occupation and occupation.title:
            params["Keyword"] = occupation.title
        if location:
            params["LocationName"] = location
        if latitude is not None:
            params["GeoLat"] = latitude
        if longitude is not None:
            params["GeoLong"] = longitude
        if radius is not None:
            params["Radius"] = radius

        response = self.session.get(
            self.endpoint,
            params=params,
            headers={"Authorization-Key": self.api_key, "User-Agent": self.user_agent},
            timeout=max(1.0, min(self.timeout_seconds, 30.0)),
        )
        response.raise_for_status()
        payload = response.json()
        records = payload.get("SearchResult", {}).get("SearchResultItems", [])
        if not isinstance(records, list):
            raise ValueError("USAJOBS returned malformed search results.")

        retrieved_at = datetime.now(timezone.utc)
        openings = []
        for record in records[: max(1, min(self.result_limit, 100))]:
            try:
                openings.append(self._normalize_record(record, retrieved_at))
            except (KeyError, TypeError, ValueError):
                continue
        return openings

    def _normalize_record(self, record: object, retrieved_at: datetime) -> dict[str, object]:
        if not isinstance(record, Mapping):
            raise TypeError("USAJOBS record must be an object.")
        descriptor = record["MatchedObjectDescriptor"]
        if not isinstance(descriptor, Mapping):
            raise TypeError("USAJOBS descriptor must be an object.")
        job_id = str(descriptor["PositionID"])
        title = str(descriptor["PositionTitle"])
        apply_url = str(descriptor["PositionURI"])
        if not job_id or not title or not apply_url:
            raise ValueError("USAJOBS record is missing required fields.")
        schedule = descriptor.get("PositionSchedule")
        schedule_name = schedule[0].get("Name") if isinstance(schedule, list) and schedule and isinstance(schedule[0], Mapping) else None
        telework = descriptor.get("TeleworkEligible")
        posted_at = descriptor.get("PublicationStartDate")
        if isinstance(posted_at, str) and len(posted_at) == 10:
            posted_at = f"{posted_at}T00:00:00+00:00"
        compensation = self._compensation(descriptor.get("PositionRemuneration"))
        return {
            "provider": self.metadata.provider,
            "provider_job_id": job_id,
            "title": title,
            "employer": descriptor.get("OrganizationName"),
            "location": descriptor.get("PositionLocationDisplay") or descriptor.get("PositionLocation"),
            "country_code": "US",
            "retrieved_at": retrieved_at,
            "source_attribution": self.metadata.attribution,
            "apply_url": apply_url,
            "compensation": compensation,
            "employment_type": schedule_name,
            "remote_or_hybrid": telework,
            "posted_at": posted_at,
        }

    @staticmethod
    def _compensation(value: object) -> dict[str, object] | None:
        if not isinstance(value, list) or not value or not isinstance(value[0], Mapping):
            return None
        record = value[0]
        interval = str(record.get("RateIntervalCode") or "").lower()
        if interval not in {"hour", "day", "week", "month", "year"}:
            interval = None

        def number(name: str) -> float | None:
            try:
                return float(record[name]) if record.get(name) is not None else None
            except (TypeError, ValueError):
                return None

        minimum = number("MinimumRange")
        maximum = number("MaximumRange")
        if minimum is None and maximum is None:
            return None
        return {
            "currency": record.get("CurrencyCode"),
            "interval": interval,
            "minimum_amount": minimum,
            "maximum_amount": maximum,
        }


def configured_usajobs_provider() -> USAJobsProvider | None:
    provider = USAJobsProvider()
    return provider if provider.configured else None