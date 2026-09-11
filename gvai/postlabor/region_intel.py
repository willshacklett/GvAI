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
        timeout=30,
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
        timeout=30,
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
        body_preview = (
            acs_response.text[:300]
            .replace("\n", " ")
            .replace("\r", " ")
        )

        raise RuntimeError(
            "Census ACS API returned a non-JSON response: "
            f"status={acs_response.status_code}, "
            f"content_type={content_type}, "
            f"body={body_preview}"
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

    home_value_to_income_ratio = None

    if (
        median_home_value is not None
        and median_income is not None
        and median_income > 0
    ):
        home_value_to_income_ratio = round(
            median_home_value / median_income,
            2,
        )

    unemployment_rate = None

    if labor_force and unemployed is not None:
        unemployment_rate = round(
            unemployed / labor_force * 100,
            1,
        )

    occupation_profile = build_county_occupation_profile(
        state_fips=state_fips,
        county_fips=county_fips,
        acs_year=acs_year,
        census_api_key=census_api_key,
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
        "home_value_to_income_ratio": home_value_to_income_ratio,
        "median_age": median_age,
        "occupation_profile": occupation_profile,
        "source": "U.S. Census Bureau ACS 5-year",
    }


ACS_OCCUPATION_GROUPS = {
    "management_business_science_arts": {
        "label": "Management, business, science, and arts",
        "variable": "S2401_C01_002E",
    },
    "service": {
        "label": "Service",
        "variable": "S2401_C01_018E",
    },
    "sales_office": {
        "label": "Sales and office",
        "variable": "S2401_C01_026E",
    },
    "natural_resources_construction_maintenance": {
        "label": "Natural resources, construction, and maintenance",
        "variable": "S2401_C01_029E",
    },
    "production_transportation_material_moving": {
        "label": "Production, transportation, and material moving",
        "variable": "S2401_C01_033E",
    },
}


def build_county_occupation_profile(
    *,
    state_fips: str,
    county_fips: str,
    acs_year: int = 2024,
    census_api_key: str | None = None,
) -> Dict[str, Any]:
    """
    Retrieve broad county occupation groups from ACS subject table S2401.

    This is the geographic bridge between county-level labor composition
    and GVAI's national occupation-demand / automation models.
    """

    key = (
        census_api_key
        or os.getenv("CENSUS_API_KEY")
        or ""
    ).strip()

    if not key:
        return {
            "data_available": False,
            "reason": "CENSUS_API_KEY is not configured.",
            "source": "U.S. Census Bureau ACS S2401",
        }

    total_variable = "S2401_C01_001E"

    variables = [
        "NAME",
        total_variable,
        *[
            item["variable"]
            for item in ACS_OCCUPATION_GROUPS.values()
        ],
    ]

    response = requests.get(
        f"{ACS_BASE}/{acs_year}/acs/acs5/subject",
        params={
            "get": ",".join(variables),
            "for": f"county:{county_fips}",
            "in": f"state:{state_fips}",
            "key": key,
        },
        timeout=30,
        headers={
            "User-Agent": "GVAI/1.0",
            "Accept": "application/json",
        },
    )

    response.raise_for_status()

    rows = response.json()

    if len(rows) < 2:
        return {
            "data_available": False,
            "source": "U.S. Census Bureau ACS S2401",
        }

    data = dict(zip(rows[0], rows[1]))

    employed_total = _number(
        data.get(total_variable)
    )

    groups = []

    for group_id, definition in ACS_OCCUPATION_GROUPS.items():
        employed = _number(
            data.get(definition["variable"])
        )

        share_percent = None

        if (
            employed_total
            and employed is not None
        ):
            share_percent = round(
                employed / employed_total * 100,
                1,
            )

        groups.append(
            {
                "group_id": group_id,
                "label": definition["label"],
                "employed": employed,
                "share_percent": share_percent,
            }
        )

    groups.sort(
        key=lambda item: (
            item["employed"]
            if item["employed"] is not None
            else -1
        ),
        reverse=True,
    )

    return {
        "data_available": True,
        "acs_year": acs_year,
        "civilian_employed_16_plus": employed_total,
        "groups": groups,
        "source": "U.S. Census Bureau ACS S2401",
    }
