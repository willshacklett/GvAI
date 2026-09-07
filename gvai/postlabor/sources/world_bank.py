from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

import requests

from gvai.postlabor.data.schema import (
    DataSource,
    Geography,
    GeographicSnapshot,
    Observation,
)


WORLD_BANK_API = "https://api.worldbank.org/v2"


INDICATORS: Dict[str, str] = {
    "demographics.fertility_rate": "SP.DYN.TFRT.IN",
    "demographics.age_65_plus_share": "SP.POP.65UP.TO.ZS",
    "demographics.working_age_share": "SP.POP.1564.TO.ZS",
    "demographics.old_age_dependency_ratio": "SP.POP.DPND.OL",
    "labor.unemployment_rate": "SL.UEM.TOTL.ZS",
    "labor.participation_rate": "SL.TLF.CACT.ZS",
    "economy.gdp_per_capita": "NY.GDP.PCAP.CD",
}


SOURCE = DataSource(
    source_id="world_bank",
    name="World Bank Open Data",
    publisher="World Bank",
    dataset="World Development Indicators",
    url="https://data.worldbank.org/",
)


def _fetch_indicator(
    country_code: str,
    indicator_code: str,
    *,
    per_page: int = 100,
) -> List[dict]:
    url = (
        f"{WORLD_BANK_API}/country/{country_code}"
        f"/indicator/{indicator_code}"
    )

    response = requests.get(
        url,
        params={
            "format": "json",
            "per_page": per_page,
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if not isinstance(payload, list) or len(payload) < 2:
        return []

    rows = payload[1]

    if not isinstance(rows, list):
        return []

    return rows


def _latest_value(rows: List[dict]) -> Optional[dict]:
    for row in rows:
        value = row.get("value")

        if value is None:
            continue

        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue

        year = str(row.get("date") or "").strip()

        if not year:
            continue

        return {
            "value": numeric_value,
            "year": year,
        }

    return None


def fetch_country_snapshot(
    country_code: str,
    country_name: Optional[str] = None,
    *,
    variable_ids: Optional[Iterable[str]] = None,
) -> GeographicSnapshot:

    code = country_code.upper().strip()

    selected = list(variable_ids or INDICATORS.keys())

    geography = Geography(
        geo_id=code,
        name=country_name or code,
        level="country",
    )

    snapshot = GeographicSnapshot(
        geography=geography,
        as_of=datetime.now(timezone.utc).date().isoformat(),
    )

    for variable_id in selected:
        indicator_code = INDICATORS.get(variable_id)

        if not indicator_code:
            continue

        rows = _fetch_indicator(
            code,
            indicator_code,
        )

        latest = _latest_value(rows)

        if latest is None:
            continue

        snapshot.add(
            Observation(
                variable_id=variable_id,
                geography=geography,
                value=latest["value"],
                observed_at=f'{latest["year"]}-01-01',
                source=SOURCE,
                confidence=0.95,
                metadata={
                    "world_bank_indicator": indicator_code,
                },
            )
        )

    return snapshot
