from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import requests


BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


@dataclass(frozen=True)
class BLSDatapoint:
    series_id: str
    year: int
    period: str
    value: float
    period_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "series_id": self.series_id,
            "year": self.year,
            "period": self.period,
            "period_name": self.period_name,
            "value": self.value,
        }


@dataclass(frozen=True)
class BLSSeries:
    series_id: str
    data: List[BLSDatapoint]

    def latest(self) -> Optional[BLSDatapoint]:
        if not self.data:
            return None

        def sort_key(item: BLSDatapoint):
            period_number = 0

            if item.period.startswith("M"):
                try:
                    period_number = int(item.period[1:])
                except ValueError:
                    period_number = 0

            return item.year, period_number

        return sorted(
            self.data,
            key=sort_key,
            reverse=True,
        )[0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "series_id": self.series_id,
            "data": [
                item.to_dict()
                for item in self.data
            ],
        }


class BLSClient:
    """
    Minimal wrapper around the BLS Public Data API.

    BLS_API_KEY is optional. Without a key the API still works,
    but the public request limits are lower.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key or os.getenv("BLS_API_KEY")
        self.timeout = timeout

    def fetch_series(
        self,
        series_ids: Iterable[str],
        *,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> List[BLSSeries]:

        ids = [
            str(series_id).strip()
            for series_id in series_ids
            if str(series_id).strip()
        ]

        if not ids:
            return []

        payload: Dict[str, Any] = {
            "seriesid": ids,
        }

        if start_year is not None:
            payload["startyear"] = str(start_year)

        if end_year is not None:
            payload["endyear"] = str(end_year)

        if self.api_key:
            payload["registrationkey"] = self.api_key

        response = requests.post(
            BLS_API_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        body = response.json()

        status = str(body.get("status") or "").upper()

        if status != "REQUEST_SUCCEEDED":
            messages = body.get("message") or []
            raise RuntimeError(
                "BLS request failed: "
                + "; ".join(str(item) for item in messages)
            )

        raw_series = (
            body.get("Results", {})
            .get("series", [])
        )

        results: List[BLSSeries] = []

        for series in raw_series:
            series_id = str(
                series.get("seriesID") or ""
            )

            datapoints: List[BLSDatapoint] = []

            for item in series.get("data") or []:
                raw_value = item.get("value")

                try:
                    value = float(raw_value)
                    year = int(item.get("year"))
                except (TypeError, ValueError):
                    continue

                datapoints.append(
                    BLSDatapoint(
                        series_id=series_id,
                        year=year,
                        period=str(
                            item.get("period") or ""
                        ),
                        period_name=str(
                            item.get("periodName") or ""
                        ),
                        value=value,
                    )
                )

            results.append(
                BLSSeries(
                    series_id=series_id,
                    data=datapoints,
                )
            )

        return results

    def fetch_latest(
        self,
        series_ids: Iterable[str],
    ) -> Dict[str, Optional[BLSDatapoint]]:
        series = self.fetch_series(series_ids)

        return {
            item.series_id: item.latest()
            for item in series
        }
