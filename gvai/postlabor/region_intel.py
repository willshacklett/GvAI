from __future__ import annotations

from typing import Any, Dict

import os
import requests


CENSUS_GEOCODER = (
    "https://geocoding.geo.census.gov/"
    "geocoder/geographies/coordinates"
)

ACS_BASE = "https://api.census.gov/data"


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_us_region(
    latitude: float,
    longitude: float,
    *,
    acs_year: int = 2024,
) -> Dict[str, Any]:
    """
    Resolve a U.S. coordinate to state/county and retrieve
    core ACS 5-year regional indicators.

    Returns supported=False when the Census geocoder does
    not identify a U.S. county.
    """

    geo_response = requests.get(
        CENSUS_GEOCODER,
        params={
            "x": longitude,
            "y": latitude,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        },
        timeout=12,
    )
    geo_response.raise_for_status()

    result = geo_response.json().get("result", {})
    geographies = result.get("geographies", {})

    counties = geographies.get("Counties") or []
    states = geographies.get("States") or []

    if not counties or not states:
        return {
            "supported": False,
            "latitude": latitude,
            "longitude": longitude,
            "reason": "No U.S. county resolved for this coordinate.",
        }

    county = counties[0]
    state = states[0]

    county_fips = str(county.get("COUNTY", "")).zfill(3)
    state_fips = str(state.get("STATE", "")).zfill(2)

    county_name = (
        county.get("NAME")
        or county.get("BASENAME")
        or "Unknown County"
    )

    state_name = (
        state.get("NAME")
        or state.get("BASENAME")
        or "Unknown State"
    )

    variables = [
        "NAME",
        "B01003_001E",
        "B23025_003E",
        "B23025_005E",
        "B19013_001E",
        "B25077_001E",
        "B01002_001E",
    ]

    census_api_key = (
        os.getenv("CENSUS_API_KEY")
        or ""
    ).strip()

    if not census_api_key:
        return {
            "supported": True,
            "data_available": False,
            "latitude": latitude,
            "longitude": longitude,
            "state": state_name,
            "county": county_name,
            "state_fips": state_fips,
            "county_fips": county_fips,
            "acs_year": acs_year,
            "reason": "CENSUS_API_KEY is not configured.",
            "source": "U.S. Census Bureau",
        }

    params = {
        "get": ",".join(variables),
        "for": f"county:{county_fips}",
        "in": f"state:{state_fips}",
        "key": census_api_key,
    }

    acs_response = requests.get(
        f"{ACS_BASE}/{acs_year}/acs/acs5",
        params=params,
        timeout=12,
        headers={
            "User-Agent": "GVAI/1.0",
            "Accept": "application/json",
        },
    )

    acs_response.raise_for_status()

    content_type = (
        acs_response.headers.get(
            "content-type",
            ""
        )
    ).lower()

    if "json" not in content_type:
        raise RuntimeError(
            "Census ACS API returned a non-JSON response."
        )

    rows = acs_response.json()

    if len(rows) < 2:
        return {
            "supported": True,
            "latitude": latitude,
            "longitude": longitude,
            "state": state_name,
            "county": county_name,
            "state_fips": state_fips,
            "county_fips": county_fips,
            "acs_year": acs_year,
            "data_available": False,
        }

    headers = rows[0]
    values = rows[1]

    data = dict(zip(headers, values))

    population = _number(data.get("B01003_001E"))
    labor_force = _number(data.get("B23025_003E"))
    unemployed = _number(data.get("B23025_005E"))
    median_income = _number(data.get("B19013_001E"))
    median_home_value = _number(data.get("B25077_001E"))
    median_age = _number(data.get("B01002_001E"))

    unemployment_rate = None

    if labor_force and unemployed is not None:
        unemployment_rate = round(
            unemployed / labor_force * 100,
            1,
        )

    return {
        "supported": True,
        "data_available": True,
        "latitude": latitude,
        "longitude": longitude,
        "state": state_name,
        "county": county_name,
        "state_fips": state_fips,
        "county_fips": county_fips,
        "acs_year": acs_year,
        "population": population,
        "labor_force": labor_force,
        "unemployed": unemployed,
        "unemployment_rate": unemployment_rate,
        "median_household_income": median_income,
        "median_home_value": median_home_value,
        "median_age": median_age,
        "source": "U.S. Census Bureau ACS 5-year",
    }
