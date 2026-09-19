"""
Deterministic Worker + Region intelligence bridge.

This module combines the existing regional labor intelligence
synthesis with existing audited STEX occupation profiles and
existing regional OEWS occupation employment, for one selected
county and one selected occupation.

V1 deliberately reports only data the current production deployment
can actually provide. It does not package a national BLS market
signal, since the underlying workbook and openpyxl dependency are
not part of the production runtime.

It intentionally does not:
  - compute a GVAI composite score
  - invent a geographic opportunity score
  - invent housing/labor/STEX thresholds
  - call an LLM or any external model
  - replace or duplicate the worker-transition system

Every unavailable signal remains explicitly "unknown" -- it is never
converted to zero or filled in with an invented value.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from requests import HTTPError, RequestException

from gvai.postlabor.labor_providers import (
    OccupationReference,
    provider_for_country,
    unavailable_evidence,
)
from gvai.postlabor.region_labor_intelligence import (
    DEFAULT_STEX_SOURCE_YEAR,
    synthesize_region_labor_intelligence,
)
from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.sources.oews import OEWSClient, format_oews_soc_code
from gvai.postlabor.stex.store import (
    InvalidSTEXOccupationCode,
    STEXProfileNotFound,
    load_occupation_stex_profile,
    normalize_occupation_code,
)

logger = logging.getLogger(__name__)

# Fixed, non-secret upstream hostname for safe diagnostic logging only.
ONET_UPSTREAM_HOST = "api-v2.onetcenter.org"


def _occupation_stex_signal(occupation_code: str) -> Dict[str, Any]:
    try:
        profile = load_occupation_stex_profile(occupation_code)
    except STEXProfileNotFound:
        return {
            "id": "occupation_stex",
            "status": "unknown",
            "profile": None,
            "explanation": (
                "No audited STEX profile exists yet for this "
                "occupation. Structural exposure is unknown, "
                "not zero."
            ),
        }

    return {
        "id": "occupation_stex",
        "status": "known",
        "profile": profile,
        "explanation": (
            "Audited structural exposure is "
            f"{profile.get('structural_exposure')} under "
            f"{profile.get('rubric_version', 'STEX')}."
        ),
    }


def _onet_soc_suffix(occupation_code: str) -> str:
    """Return the O*NET-SOC detail suffix, e.g. "11-9199.11" -> "11"."""
    code = str(occupation_code or "").strip()
    if "." in code:
        return code.split(".", 1)[1]
    return "00"


def _occupation_regional_employment_signal(
    oews_area_code: str | None,
    occupation_code: str,
    *,
    stex_year: int,
) -> Dict[str, Any]:
    if not oews_area_code:
        return {
            "id": "occupation_regional_employment",
            "status": "unknown",
            "employment": None,
            "occupation_title": None,
            "oews_occupation_code": None,
            "match_specificity": None,
            "explanation": (
                "No packaged OEWS labor-market area is available "
                "for this county, so local employment for this "
                "occupation is unknown."
            ),
        }

    try:
        normalized_soc = format_oews_soc_code(occupation_code)
    except ValueError:
        normalized_soc = None

    try:
        client = OEWSClient()
        _total, rows = client.fetch_catalog_regional_employment(
            area_code=oews_area_code,
            source_year=stex_year,
        )
    except RuntimeError:
        return {
            "id": "occupation_regional_employment",
            "status": "unknown",
            "employment": None,
            "occupation_title": None,
            "oews_occupation_code": None,
            "match_specificity": None,
            "explanation": (
                "Regional OEWS employment data has not been "
                "refreshed for this area and year, so local "
                "employment for this occupation is unknown."
            ),
        }

    match = None
    if normalized_soc is not None:
        for row in rows:
            try:
                row_soc = format_oews_soc_code(row.occupation_code)
            except ValueError:
                continue
            if row_soc == normalized_soc:
                match = row
                break

    if match is None:
        return {
            "id": "occupation_regional_employment",
            "status": "unknown",
            "employment": None,
            "occupation_title": None,
            "oews_occupation_code": None,
            "match_specificity": None,
            "explanation": (
                "This occupation is not present in the packaged "
                "regional OEWS employment snapshot, so local "
                "employment is unknown."
            ),
        }

    # OEWS only publishes employment at the 6-digit SOC level. Any O*NET-SOC
    # code with a detail suffix other than ".00" is one of several detailed
    # O*NET occupations sharing a single, broader published SOC group, so the
    # matched employment number describes that whole SOC group, not this
    # detailed occupation alone.
    is_broader_category = _onet_soc_suffix(occupation_code) != "00"

    if is_broader_category:
        return {
            "id": "occupation_regional_employment",
            "status": "known",
            "employment": match.employment,
            "occupation_title": match.occupation_title,
            "oews_occupation_code": normalized_soc,
            "match_specificity": "broader_category",
            "source_year": stex_year,
            "explanation": (
                f"OEWS does not publish employment specific to "
                f"{occupation_code}. This figure of {match.employment} is "
                f"the broader published OEWS category "
                f'"{match.occupation_title}" ({normalized_soc}) within '
                f"this labor-market area."
            ),
        }

    return {
        "id": "occupation_regional_employment",
        "status": "known",
        "employment": match.employment,
        "occupation_title": match.occupation_title,
        "oews_occupation_code": normalized_soc,
        "match_specificity": "exact",
        "source_year": stex_year,
        "explanation": (
            f"Regional employment in this occupation is estimated "
            f"at {match.employment} within this labor-market area."
        ),
    }


def _occupation_regional_wage_signal(
    oews_area_code: str | None,
    occupation_code: str,
    *,
    wage_year: int,
) -> Dict[str, Any]:
    """Return the packaged official OEWS median wage evidence, if any.

    Reads only the packaged local wage snapshot. Suppressed or missing
    wage figures remain None -- they are never reported as zero or
    replaced with a placeholder.
    """
    unknown_base = {
        "id": "occupation_regional_wage",
        "status": "unknown",
        "median_hourly_wage": None,
        "median_annual_wage": None,
        "year": None,
        "source": None,
        "occupation_title": None,
        "oews_occupation_code": None,
        "match_specificity": None,
    }

    if not oews_area_code:
        return {
            **unknown_base,
            "explanation": (
                "No packaged OEWS labor-market area is available "
                "for this county, so regional median wage for this "
                "occupation is unknown."
            ),
        }

    try:
        normalized_soc = format_oews_soc_code(occupation_code)
    except ValueError:
        normalized_soc = None

    try:
        client = OEWSClient()
        rows = client.fetch_catalog_regional_wages(
            area_code=oews_area_code,
            source_year=wage_year,
        )
    except RuntimeError:
        return {
            **unknown_base,
            "explanation": (
                "Regional OEWS median wage data has not been "
                "packaged for this area and year, so it is unknown."
            ),
        }

    match = None
    if normalized_soc is not None:
        for row in rows:
            try:
                row_soc = format_oews_soc_code(row.occupation_code)
            except ValueError:
                continue
            if row_soc == normalized_soc:
                match = row
                break

    if match is None:
        return {
            **unknown_base,
            "explanation": (
                "This occupation is not present in the packaged "
                "regional OEWS median wage snapshot, so its wage is "
                "unknown."
            ),
        }

    is_broader_category = _onet_soc_suffix(occupation_code) != "00"
    both_missing = (
        match.median_hourly_wage is None and match.median_annual_wage is None
    )

    known_fields = {
        "median_hourly_wage": match.median_hourly_wage,
        "median_annual_wage": match.median_annual_wage,
        "year": wage_year,
        "source": match.source,
        "occupation_title": match.occupation_title,
        "oews_occupation_code": normalized_soc,
        "match_specificity": (
            "broader_category" if is_broader_category else "exact"
        ),
    }

    if both_missing:
        broader_note = (
            f' for the broader OEWS category "{match.occupation_title}" '
            f"({normalized_soc})"
            if is_broader_category
            else ""
        )
        return {
            "id": "occupation_regional_wage",
            "status": "suppressed",
            **known_fields,
            "explanation": (
                "BLS suppressed or did not publish a median wage"
                f"{broader_note} for this area and year, so the wage "
                "is unavailable, not zero."
            ),
        }

    if is_broader_category:
        explanation = (
            f"OEWS does not publish a median wage specific to "
            f"{occupation_code}. This wage is the broader published "
            f'OEWS category "{match.occupation_title}" ({normalized_soc}) '
            "within this labor-market area, not this detailed occupation."
        )
    else:
        explanation = (
            "This is the occupation's regional OEWS median wage within "
            "this labor-market area."
        )

    return {
        "id": "occupation_regional_wage",
        "status": "known",
        **known_fields,
        "explanation": explanation,
    }


def _build_worker_outlook_summary(
    *,
    region: Dict[str, Any],
    occupation_code: str,
    occupation_title: str | None,
    stex_signal: Dict[str, Any],
    employment_signal: Dict[str, Any],
    wage_signal: Dict[str, Any],
) -> str:
    title = occupation_title or occupation_code
    county = region.get("county") or "this region"

    parts = [f"Worker outlook for {title} in {county}"]

    if stex_signal["status"] == "known":
        profile = stex_signal["profile"] or {}
        parts.append(
            "audited structural exposure is "
            f"{profile.get('structural_exposure')} under "
            f"{profile.get('rubric_version', 'STEX')}"
        )
    else:
        parts.append(
            "STEX structural exposure is unknown for this occupation"
        )

    if employment_signal["status"] == "known":
        if employment_signal.get("match_specificity") == "broader_category":
            parts.append(
                "regional employment for the broader OEWS category "
                f'"{employment_signal.get("occupation_title")}" is '
                f"{employment_signal['employment']} (not specific to "
                "this detailed occupation)"
            )
        else:
            parts.append(
                "regional employment in this occupation is estimated at "
                f"{employment_signal['employment']}"
            )
    else:
        parts.append(
            "regional employment for this occupation is unknown"
        )

    if wage_signal["status"] == "known":
        wage_bits = []
        if wage_signal.get("median_hourly_wage") is not None:
            wage_bits.append(f"${wage_signal['median_hourly_wage']}/hr")
        if wage_signal.get("median_annual_wage") is not None:
            wage_bits.append(f"${wage_signal['median_annual_wage']}/yr")
        wage_text = " and ".join(wage_bits) if wage_bits else "unavailable"
        if wage_signal.get("match_specificity") == "broader_category":
            parts.append(
                "regional median wage for the broader OEWS category "
                f'"{wage_signal.get("occupation_title")}" is {wage_text} '
                "(not specific to this detailed occupation)"
            )
        else:
            parts.append(
                f"the occupation's regional OEWS median wage is {wage_text}"
            )
    elif wage_signal["status"] == "suppressed":
        parts.append(
            "regional median wage for this occupation is suppressed by "
            "BLS, not zero"
        )
    else:
        parts.append(
            "regional median wage for this occupation is unknown"
        )

    return "; ".join(parts) + "."


def synthesize_worker_region_outlook(
    latitude: float,
    longitude: float,
    occupation_code: str,
    *,
    acs_year: int = 2024,
    stex_year: int = DEFAULT_STEX_SOURCE_YEAR,
    country_code: str = "US",
) -> Dict[str, Any]:
    """
    Deterministically combine existing regional labor intelligence
    with an existing audited occupation STEX profile (when
    available) for one selected county and one selected occupation.

    Raises InvalidSTEXOccupationCode if occupation_code is not a
    valid O*NET-SOC code. Never invents a composite score or a
    geographic opportunity score.
    """

    provider = provider_for_country(country_code)
    if provider is None:
        return {
            "supported": False,
            "country_code": str(country_code).strip().upper(),
            "occupation_code": occupation_code,
            "reason": unavailable_evidence(
                "occupation_profiles", country_code
            )["reason"],
            "occupation": {
                "stex": unavailable_evidence(
                    "structural_exposure", country_code
                ),
                "regional_employment": unavailable_evidence(
                    "employment", country_code
                ),
                "regional_wage": unavailable_evidence("wages", country_code),
            },
        }

    normalized_code = normalize_occupation_code(occupation_code)

    region = synthesize_region_labor_intelligence(
        latitude,
        longitude,
        acs_year=acs_year,
        stex_year=stex_year,
    )

    if not region.get("supported"):
        return {
            "supported": False,
            "latitude": latitude,
            "longitude": longitude,
            "occupation_code": normalized_code,
            "reason": region.get(
                "reason",
                "No U.S. county resolved for this coordinate.",
            ),
        }

    stex_signal = _occupation_stex_signal(normalized_code)
    employment_signal = _occupation_regional_employment_signal(
        region.get("oews_area_code"),
        normalized_code,
        stex_year=stex_year,
    )
    wage_signal = _occupation_regional_wage_signal(
        region.get("oews_area_code"),
        normalized_code,
        wage_year=stex_year,
    )

    occupation_title = (
        (stex_signal.get("profile") or {}).get("occupation_title")
        or employment_signal.get("occupation_title")
        or wage_signal.get("occupation_title")
    )

    constraints = list(region.get("constraints") or [])

    for signal in (stex_signal, employment_signal, wage_signal):
        if signal["status"] in ("unknown", "suppressed"):
            constraints.append(signal["explanation"])

    summary = _build_worker_outlook_summary(
        region=region,
        occupation_code=normalized_code,
        occupation_title=occupation_title,
        stex_signal=stex_signal,
        employment_signal=employment_signal,
        wage_signal=wage_signal,
    )

    sources = list(region.get("sources") or [])

    if stex_signal["status"] == "known":
        sources.append({
            "name": "GVAI STEX audited occupation profile",
            "vintage": (
                (stex_signal["profile"] or {}).get("source") or {}
            ).get("tasks_year"),
        })

    return {
        "supported": True,
        "data_available": bool(region.get("data_available")),
        "latitude": latitude,
        "longitude": longitude,
        "country_code": provider.country_code,
        "provider": provider.to_dict(),
        "state": region.get("state"),
        "county": region.get("county"),
        "state_fips": region.get("state_fips"),
        "county_fips": region.get("county_fips"),
        "acs_year": acs_year,
        "oews_area_code": region.get("oews_area_code"),
        "occupation_code": normalized_code,
        "occupation_title": occupation_title,
        "occupation_reference": (
            OccupationReference(
                country_code=provider.country_code,
                provider=provider.provider,
                provider_occupation_code=normalized_code,
                title=occupation_title,
            ).to_dict()
            if occupation_title
            else None
        ),
        "region": region,
        "occupation": {
            "stex": stex_signal,
            "regional_employment": employment_signal,
            "regional_wage": wage_signal,
        },
        "worker_outlook": {
            "summary": summary,
        },
        "constraints": constraints,
        "sources": sources,
    }


def synthesize_worker_related_occupations(
    latitude: float,
    longitude: float,
    occupation_code: str,
    *,
    acs_year: int = 2024,
    stex_year: int = DEFAULT_STEX_SOURCE_YEAR,
    onet_client: OnetClient | None = None,
    country_code: str = "US",
) -> Dict[str, Any]:
    """Return O*NET related occupations with only available local facts."""
    provider = provider_for_country(country_code)
    if provider is None:
        return {
            "supported": False,
            "country_code": str(country_code).strip().upper(),
            "occupation_code": occupation_code,
            "reason": unavailable_evidence(
                "occupation_profiles", country_code
            )["reason"],
            "related_occupations": {
                "status": "unavailable",
                "items": [],
                "explanation": unavailable_evidence(
                    "occupation_profiles", country_code
                )["reason"],
            },
        }
    normalized_code = normalize_occupation_code(occupation_code)
    region = synthesize_region_labor_intelligence(
        latitude,
        longitude,
        acs_year=acs_year,
        stex_year=stex_year,
    )

    if not region.get("supported"):
        return {
            "supported": False,
            "latitude": latitude,
            "longitude": longitude,
            "occupation_code": normalized_code,
            "reason": region.get(
                "reason",
                "No U.S. county resolved for this coordinate.",
            ),
        }

    try:
        client = onet_client or OnetClient()
        related_occupations = client.related_occupations(normalized_code)
    except (RuntimeError, RequestException, ValueError, LookupError) as exc:
        status_code = None
        if isinstance(exc, HTTPError) and exc.response is not None:
            status_code = exc.response.status_code

        # Safe diagnostic only: no keys, headers, or URLs are ever logged.
        logger.warning(
            "O*NET related_occupations request failed "
            "(exception_class=%s, upstream_host=%s, "
            "occupation_code=%s, upstream_status_code=%s)",
            type(exc).__name__,
            ONET_UPSTREAM_HOST,
            normalized_code,
            status_code,
        )

        return {
            "supported": True,
            "data_available": bool(region.get("data_available")),
            "latitude": latitude,
            "longitude": longitude,
            "county": region.get("county"),
            "occupation_code": normalized_code,
            "related_occupations": {
                "status": "unavailable",
                "items": [],
                "explanation": (
                    "O*NET Related Occupations is unavailable for this "
                    "selection, so no related occupations are shown."
                ),
            },
            "constraints": list(region.get("constraints") or []),
            "sources": list(region.get("sources") or []),
        }

    constraints = list(region.get("constraints") or [])
    items = []

    for related in related_occupations:
        try:
            related_code = normalize_occupation_code(
                related.occupation_code
            )
        except InvalidSTEXOccupationCode:
            continue

        stex_signal = _occupation_stex_signal(related_code)
        employment_signal = _occupation_regional_employment_signal(
            region.get("oews_area_code"),
            related_code,
            stex_year=stex_year,
        )
        wage_signal = _occupation_regional_wage_signal(
            region.get("oews_area_code"),
            related_code,
            wage_year=stex_year,
        )

        for signal in (stex_signal, employment_signal, wage_signal):
            if signal["status"] in ("unknown", "suppressed") and signal["explanation"] not in constraints:
                constraints.append(signal["explanation"])

        items.append({
            "occupation_code": related_code,
            "occupation_title": related.title,
            "relationship_source": "O*NET Related Occupations",
            "relationship_metadata": {
                "bright_outlook": related.bright_outlook,
            },
            "stex": stex_signal,
            "regional_employment": employment_signal,
            "regional_wage": wage_signal,
        })

    sources = list(region.get("sources") or [])
    sources.append({"name": "O*NET Related Occupations"})

    return {
        "supported": True,
        "data_available": bool(region.get("data_available")),
        "latitude": latitude,
        "longitude": longitude,
        "country_code": provider.country_code,
        "provider": provider.to_dict(),
        "county": region.get("county"),
        "occupation_code": normalized_code,
        "related_occupations": {
            "status": "known",
            "items": items,
            "explanation": (
                "Displayed in O*NET source order. GVAI does not re-rank "
                "these occupations."
            ),
        },
        "constraints": constraints,
        "sources": sources,
    }


__all__ = [
    "InvalidSTEXOccupationCode",
    "synthesize_worker_related_occupations",
    "synthesize_worker_region_outlook",
]
