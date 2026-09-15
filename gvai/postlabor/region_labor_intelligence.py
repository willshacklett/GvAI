"""
Deterministic Regional Labor Intelligence synthesis.

This module turns existing factual regional signals (ACS labor
availability, workforce mix, housing pressure, and packaged regional
STEX coverage) into an explainable structure for the UI.

It intentionally does not:
  - invent missing data (unknown stays unknown, never zero)
  - compute a 0-100 GVAI score or any other composite score
  - label a region "good" or "bad"
  - call an LLM or any external model

Every returned signal keeps the underlying values it was derived
from so a caller (or the UI) can explain why an observation was
produced.
"""

from __future__ import annotations

from typing import Any, Dict

from gvai.postlabor.region_intel import (
    classify_labor_availability,
    resolve_us_region,
)
from gvai.postlabor.sources.oews import OEWSClient
from gvai.postlabor.stex.regional import build_regional_stex_coverage_plan
from gvai.postlabor.stex.store import list_occupation_stex_profiles


DEFAULT_STEX_SOURCE_YEAR = 2025
HOUSING_PRESSURE_MEASURE = (
    "median_home_value_to_median_household_income"
)


def _labor_availability_signal(region: Dict[str, Any]) -> Dict[str, Any]:
    unemployment_rate = region.get("unemployment_rate")
    classification = classify_labor_availability(unemployment_rate)
    known = unemployment_rate is not None

    explanation = (
        f"Unemployment rate of {unemployment_rate}% classifies as "
        f"'{classification}' local labor availability."
        if known
        else (
            "Unemployment rate is unavailable, so labor availability "
            "cannot be classified."
        )
    )

    return {
        "id": "labor_availability",
        "label": "Labor Availability",
        "status": "known" if known else "unknown",
        "classification": classification,
        "values": {
            "labor_force": region.get("labor_force"),
            "unemployed": region.get("unemployed"),
            "unemployment_rate": unemployment_rate,
        },
        "explanation": explanation,
    }


def _workforce_mix_signal(region: Dict[str, Any]) -> Dict[str, Any]:
    profile = region.get("occupation_profile") or {}
    groups = profile.get("groups") or []

    known_groups = [
        group
        for group in groups
        if group.get("share_percent") is not None
    ]

    if not profile.get("data_available") or not known_groups:
        return {
            "id": "workforce_mix",
            "label": "Workforce Mix",
            "status": "unknown",
            "classification": "unknown",
            "values": {
                "civilian_employed_16_plus": profile.get(
                    "civilian_employed_16_plus"
                ),
                "groups": groups,
            },
            "explanation": (
                "Occupation-group composition is unavailable for this "
                "county."
            ),
        }

    top_group = known_groups[0]

    return {
        "id": "workforce_mix",
        "label": "Workforce Mix",
        "status": "known",
        "classification": top_group.get("group_id"),
        "values": {
            "civilian_employed_16_plus": profile.get(
                "civilian_employed_16_plus"
            ),
            "top_group": top_group.get("label"),
            "top_group_share_percent": top_group.get("share_percent"),
            "groups": groups,
        },
        "explanation": (
            f"'{top_group.get('label')}' is the largest broad "
            "occupation group, representing "
            f"{top_group.get('share_percent')}% of civilian "
            "employment 16 and older."
        ),
    }


def _housing_pressure_signal(region: Dict[str, Any]) -> Dict[str, Any]:
    ratio = region.get("home_value_to_income_ratio")
    known = ratio is not None

    explanation = (
        f"Median home value is {ratio}x median household income. "
        "The existing regional dataset reports this ratio as a fact "
        "and does not define pressure categories."
        if known
        else (
            "Median home value or median household income is "
            "unavailable, so the housing ratio is unknown."
        )
    )

    return {
        "id": "housing_pressure",
        "label": "Housing Pressure",
        "status": "known" if known else "unknown",
        "classification": "observed" if known else "unknown",
        "values": {
            "measure": HOUSING_PRESSURE_MEASURE,
            "median_household_income": region.get(
                "median_household_income"
            ),
            "median_home_value": region.get("median_home_value"),
            "home_value_to_income_ratio": ratio,
        },
        "explanation": explanation,
    }


def _regional_stex_signal(
    oews_area_code: str | None,
    *,
    stex_year: int,
) -> Dict[str, Any]:
    if not oews_area_code:
        return {
            "id": "regional_stex_coverage",
            "label": "Regional STEX Coverage",
            "status": "unknown",
            "classification": "unknown",
            "values": {},
            "explanation": (
                "No packaged OEWS labor-market area is available for "
                "this county, so regional STEX coverage is unknown."
            ),
        }

    try:
        client = OEWSClient()
        total, rows = client.fetch_catalog_regional_employment(
            area_code=oews_area_code,
            source_year=stex_year,
        )

        if total is None:
            raise RuntimeError("missing regional OEWS denominator")

        profiles = list_occupation_stex_profiles()

        occupation_titles = {
            row.occupation_code: row.occupation_title
            for row in rows
            if row.occupation_title
        }

        plan = build_regional_stex_coverage_plan(
            total_employment=total,
            employment_rows=rows,
            profiles=profiles,
            occupation_titles=occupation_titles,
            recommendation_limit=0,
        )

        return {
            "id": "regional_stex_coverage",
            "label": "Regional STEX Coverage",
            "status": "known",
            "classification": "partial_coverage",
            "values": {
                "oews_area_code": oews_area_code,
                "source_year": plan.source_year,
                "total_employment": plan.total_employment,
                "stex_covered_employment": plan.covered_employment,
                "coverage_percentage": plan.coverage_rate,
                "covered_occupation_stex": plan.covered_stex,
            },
            "explanation": (
                "STEX is aggregated only over audited occupations, "
                f"covering {plan.coverage_rate}% of total regional "
                "employment. Unrated employment is unknown, not zero."
            ),
        }

    except RuntimeError:
        return {
            "id": "regional_stex_coverage",
            "label": "Regional STEX Coverage",
            "status": "unknown",
            "classification": "unknown",
            "values": {
                "oews_area_code": oews_area_code,
            },
            "explanation": (
                "Regional OEWS employment data has not been refreshed "
                "for this area and year, so STEX coverage is unknown."
            ),
        }


def _build_summary(
    *,
    region: Dict[str, Any],
    labor_signal: Dict[str, Any],
    workforce_signal: Dict[str, Any],
    housing_signal: Dict[str, Any],
    stex_signal: Dict[str, Any],
) -> str:
    county = region.get("county") or "This county"
    parts = [f"{county} regional labor signals"]

    if labor_signal["status"] == "known":
        parts.append(
            "labor availability is "
            f"{labor_signal['classification']} "
            f"({labor_signal['values']['unemployment_rate']}% "
            "unemployment)"
        )
    else:
        parts.append("labor availability is unknown")

    if workforce_signal["status"] == "known":
        parts.append(
            "workforce is led by "
            f"{workforce_signal['values']['top_group']} "
            f"({workforce_signal['values']['top_group_share_percent']}%)"
        )
    else:
        parts.append("workforce mix is unknown")

    if housing_signal["status"] == "known":
        parts.append(
            "median home value is "
            f"{housing_signal['values']['home_value_to_income_ratio']}x "
            "median household income"
        )
    else:
        parts.append("the housing value-to-income ratio is unknown")

    if stex_signal["status"] == "known":
        parts.append(
            "regional STEX audit coverage is "
            f"{stex_signal['values']['coverage_percentage']}% of "
            "employment"
        )
    else:
        parts.append("regional STEX coverage is unknown")

    return "; ".join(parts) + "."


def synthesize_region_labor_intelligence(
    latitude: float,
    longitude: float,
    *,
    acs_year: int = 2024,
    stex_year: int = DEFAULT_STEX_SOURCE_YEAR,
) -> Dict[str, Any]:
    """
    Deterministically synthesize existing regional labor signals for
    a U.S. county into an explainable structure.

    This calls only existing, already-vetted data resolvers
    (resolve_us_region and packaged regional STEX coverage). It never
    invents missing data and never produces a composite score.
    """

    region = resolve_us_region(
        latitude=latitude,
        longitude=longitude,
        acs_year=acs_year,
    )

    if not region.get("supported"):
        return {
            "supported": False,
            "latitude": latitude,
            "longitude": longitude,
            "reason": region.get(
                "reason",
                "No U.S. county resolved for this coordinate.",
            ),
        }

    if not region.get("data_available"):
        return {
            "supported": True,
            "data_available": False,
            "latitude": latitude,
            "longitude": longitude,
            "state": region.get("state"),
            "county": region.get("county"),
            "state_fips": region.get("state_fips"),
            "county_fips": region.get("county_fips"),
            "acs_year": acs_year,
            "summary": (
                "Regional labor intelligence is unavailable because "
                "ACS data could not be retrieved for this county."
            ),
            "signals": [],
            "constraints": [
                region.get(
                    "reason",
                    "ACS data is unavailable for this county.",
                )
            ],
            "sources": [],
        }

    oews_area_code = region.get("oews_area_code")

    labor_signal = _labor_availability_signal(region)
    workforce_signal = _workforce_mix_signal(region)
    housing_signal = _housing_pressure_signal(region)
    stex_signal = _regional_stex_signal(
        oews_area_code,
        stex_year=stex_year,
    )

    signals = [
        labor_signal,
        workforce_signal,
        housing_signal,
        stex_signal,
    ]

    constraints = [
        signal["explanation"]
        for signal in signals
        if signal["status"] == "unknown"
    ]

    summary = _build_summary(
        region=region,
        labor_signal=labor_signal,
        workforce_signal=workforce_signal,
        housing_signal=housing_signal,
        stex_signal=stex_signal,
    )

    sources = [
        {
            "name": "U.S. Census Bureau ACS 5-year",
            "vintage": acs_year,
        },
    ]

    if stex_signal["status"] == "known":
        sources.append({
            "name": "BLS OEWS employment (packaged snapshot)",
            "vintage": stex_signal["values"].get("source_year"),
        })

    return {
        "supported": True,
        "data_available": True,
        "latitude": latitude,
        "longitude": longitude,
        "state": region.get("state"),
        "county": region.get("county"),
        "state_fips": region.get("state_fips"),
        "county_fips": region.get("county_fips"),
        "acs_year": acs_year,
        "oews_area_code": oews_area_code,
        "summary": summary,
        "signals": signals,
        "constraints": constraints,
        "sources": sources,
    }
