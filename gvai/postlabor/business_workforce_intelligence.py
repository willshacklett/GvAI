from __future__ import annotations

from typing import Any, Iterable, Mapping

from gvai.safety_boundary import SafetySystemsBoundary
from gvai.postlabor.labor_providers import provider_for_country, unavailable_evidence
from gvai.postlabor.region_labor_intelligence import synthesize_region_labor_intelligence
from gvai.postlabor.sources.oews import OEWSClient, normalize_soc_code
from gvai.postlabor.stex.store import (
    InvalidSTEXOccupationCode,
    STEXProfileNotFound,
    load_occupation_stex_profile,
    normalize_occupation_code,
)
from gvai.postlabor.worker_transition_preparation import (
    synthesize_worker_transition_preparation_evidence,
)


DEFAULT_BUSINESS_STEX_YEAR = 2025


def _unsupported_country_payload(country_code: str) -> dict[str, Any] | None:
    normalized = str(country_code or "US").strip().upper()
    if provider_for_country(normalized) is not None:
        return None
    evidence = {
        capability: unavailable_evidence(capability, normalized)
        for capability in (
            "occupation_profiles",
            "employment",
            "wages",
            "preparation",
            "structural_exposure",
        )
    }
    return {
        "supported": False,
        "country_code": normalized,
        "reason": evidence["employment"]["reason"],
        "evidence": evidence,
    }


def _find_code(rows: Iterable[Any], occupation_code: str) -> Any | None:
    wanted = normalize_soc_code(occupation_code)
    for row in rows:
        if normalize_soc_code(row.occupation_code) == wanted:
            return row
    return None


def _oews_match(
    rows: Iterable[Any],
    occupation_code: str,
) -> tuple[Any | None, dict[str, Any]]:
    exact = _find_code(rows, occupation_code)
    if exact is not None:
        return exact, {
            "status": "exact",
            "requested_occupation_code": occupation_code,
            "matched_occupation_code": exact.occupation_code,
            "disclosure": "Exact OEWS occupation evidence is available for this occupation.",
        }

    broader_code = f"{occupation_code.split('-', 1)[0]}-0000.00"
    broader = _find_code(rows, broader_code)
    if broader is not None:
        return broader, {
            "status": "broader_category",
            "requested_occupation_code": occupation_code,
            "matched_occupation_code": broader.occupation_code,
            "disclosure": (
                "The requested detailed O*NET occupation does not have a matching "
                "OEWS row in the packaged regional snapshot. GVAI is showing the "
                "available broader OEWS category and labels it as broader evidence."
            ),
        }

    return None, {
        "status": "unavailable",
        "requested_occupation_code": occupation_code,
        "matched_occupation_code": None,
        "disclosure": "No packaged regional OEWS employment or wage evidence is available for this occupation.",
    }


def _employment_evidence(
    client: OEWSClient,
    *,
    area_code: str | None,
    occupation_code: str,
    source_year: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not area_code:
        specificity = {
            "status": "unavailable",
            "requested_occupation_code": occupation_code,
            "matched_occupation_code": None,
            "disclosure": "No packaged OEWS labor-market area is available for this region.",
        }
        return {
            "status": "unavailable",
            "employment": None,
            "source_year": None,
            "source": None,
            "catalog_source": None,
            "series_id": None,
            "occupation_title": None,
        }, specificity

    try:
        _, rows = client.fetch_catalog_regional_employment(
            area_code=area_code,
            source_year=source_year,
        )
    except RuntimeError:
        specificity = {
            "status": "unavailable",
            "requested_occupation_code": occupation_code,
            "matched_occupation_code": None,
            "disclosure": "Packaged regional OEWS employment evidence is unavailable for this area and year.",
        }
        return {
            "status": "unavailable",
            "employment": None,
            "source_year": None,
            "source": None,
            "catalog_source": None,
            "series_id": None,
            "occupation_title": None,
        }, specificity

    match, specificity = _oews_match(rows, occupation_code)
    if match is None:
        return {
            "status": "unavailable",
            "employment": None,
            "source_year": None,
            "source": None,
            "catalog_source": None,
            "series_id": None,
            "occupation_title": None,
        }, specificity

    return {
        "status": "known",
        "employment": match.employment,
        "source_year": match.year,
        "source": match.source,
        "catalog_source": match.catalog_source,
        "series_id": match.series_id,
        "occupation_title": match.occupation_title,
    }, specificity


def _wage_evidence(
    client: OEWSClient,
    *,
    area_code: str | None,
    occupation_code: str,
    source_year: int,
    specificity: Mapping[str, Any],
) -> dict[str, Any]:
    if not area_code:
        return {
            "status": "unavailable",
            "median_hourly_wage": None,
            "median_annual_wage": None,
            "source_year": None,
            "source": None,
            "catalog_source": None,
            "occupation_title": None,
        }

    try:
        rows = client.fetch_catalog_regional_wages(
            area_code=area_code,
            source_year=source_year,
        )
    except RuntimeError:
        return {
            "status": "unavailable",
            "median_hourly_wage": None,
            "median_annual_wage": None,
            "source_year": None,
            "source": None,
            "catalog_source": None,
            "occupation_title": None,
        }

    match_code = specificity.get("matched_occupation_code") or occupation_code
    match = _find_code(rows, str(match_code))
    if match is None:
        return {
            "status": "unavailable",
            "median_hourly_wage": None,
            "median_annual_wage": None,
            "source_year": None,
            "source": None,
            "catalog_source": None,
            "occupation_title": None,
        }

    if match.median_hourly_wage is None and match.median_annual_wage is None:
        status = "unavailable"
    else:
        status = "known"

    return {
        "status": status,
        "median_hourly_wage": match.median_hourly_wage,
        "median_annual_wage": match.median_annual_wage,
        "source_year": match.year,
        "source": match.source,
        "catalog_source": match.catalog_source,
        "occupation_title": match.occupation_title,
    }


def _stex_evidence(occupation_code: str) -> dict[str, Any]:
    try:
        profile = load_occupation_stex_profile(occupation_code)
    except STEXProfileNotFound:
        return {
            "status": "unavailable",
            "structural_exposure": None,
            "augmentation_likelihood": None,
            "rated_task_count": None,
            "unrated_task_count": None,
            "rubric_version": None,
            "review_status": None,
            "source": None,
            "semantics": (
                "STEX is structural exposure evidence. It is not a probability "
                "that an occupation disappears, a probability that an employee "
                "loses a job, percent automatable, or a staffing-reduction recommendation."
            ),
        }

    return {
        "status": "known",
        "structural_exposure": profile.get("structural_exposure"),
        "augmentation_likelihood": profile.get("augmentation_likelihood"),
        "rated_task_count": profile.get("rated_task_count"),
        "unrated_task_count": profile.get("unrated_task_count"),
        "rubric_version": profile.get("rubric_version"),
        "review_status": profile.get("review_status"),
        "source": profile.get("source"),
        "semantics": (
            "STEX is structural exposure evidence. It is not a probability "
            "that an occupation disappears, a probability that an employee "
            "loses a job, percent automatable, or a staffing-reduction recommendation."
        ),
    }


def _preparation_evidence(
    occupation_code: str,
    *,
    occupation_title: str | None,
) -> dict[str, Any]:
    result = synthesize_worker_transition_preparation_evidence(
        occupation_code,
        occupation_code,
        source_occupation_title=occupation_title,
        target_occupation_title=occupation_title,
    )
    evidence = result["target_preparation"]
    return {
        "status": "known"
        if evidence["job_zone"]["status"] == "known" or evidence["education"]["status"] == "known"
        else "unavailable",
        "occupation_code": occupation_code,
        "job_zone": evidence["job_zone"],
        "education": evidence["education"],
        "source_attribution": result["source_attribution"],
        "explanation": result["explanation"],
        "constraints": result["constraints"],
    }


def synthesize_business_workforce_intelligence(
    *,
    latitude: float,
    longitude: float,
    occupation_code: str,
    occupation_title: str | None = None,
    country_code: str = "US",
    oews_year: int = DEFAULT_BUSINESS_STEX_YEAR,
    acs_year: int = 2024,
    oews_client: OEWSClient | None = None,
    safety_boundary: SafetySystemsBoundary | None = None,
) -> dict[str, Any]:
    normalized_country = str(country_code or "US").strip().upper()
    unsupported = _unsupported_country_payload(normalized_country)
    if unsupported:
        return unsupported

    normalized_code = normalize_occupation_code(occupation_code)
    client = oews_client or OEWSClient()

    region = synthesize_region_labor_intelligence(
        latitude,
        longitude,
        acs_year=acs_year,
        stex_year=oews_year,
    )

    area_code = region.get("oews_area_code") if region.get("supported") else None
    employment, specificity = _employment_evidence(
        client,
        area_code=area_code,
        occupation_code=normalized_code,
        source_year=oews_year,
    )
    wage = _wage_evidence(
        client,
        area_code=area_code,
        occupation_code=normalized_code,
        source_year=oews_year,
        specificity=specificity,
    )
    stex = _stex_evidence(normalized_code)
    preparation = _preparation_evidence(
        normalized_code,
        occupation_title=occupation_title or employment.get("occupation_title"),
    )
    safety_decision = (safety_boundary or SafetySystemsBoundary()).decide(
        "business_workforce_intelligence_status",
        context={
            "country_code": normalized_country,
            "occupation_code": normalized_code,
            "latitude": latitude,
            "longitude": longitude,
        },
    )

    constraints = []
    constraints.extend(region.get("constraints") or [])
    for label, evidence in (
        ("regional employment", employment),
        ("regional wage", wage),
        ("STEX", stex),
        ("preparation", preparation),
    ):
        if evidence.get("status") == "unavailable":
            constraints.append(f"{label} evidence is unavailable, not zero.")

    return {
        "supported": True,
        "country_code": normalized_country,
        "latitude": latitude,
        "longitude": longitude,
        "region": region,
        "occupation": {
            "occupation_code": normalized_code,
            "occupation_title": occupation_title or employment.get("occupation_title") or normalized_code,
        },
        "occupation_evidence": {
            "employment": employment,
            "wage": wage,
            "oews_specificity": specificity,
            "stex": stex,
            "preparation": preparation,
        },
        "safety_systems": {
            **safety_decision.to_dict(),
            "entry_point": "GVAI Safety Systems boundary",
            "note": (
                "This repository exposes the integration boundary only. It does not "
                "copy the Safety Systems implementation or claim active governance "
                "when no external decider is configured."
            ),
        },
        "methodology": {
            "business_score": None,
            "composite_score": None,
            "ordering": "Employer-selected order only; GVAI does not rank occupations in Business V1.",
            "missing_data": "Unavailable evidence remains unavailable and is never replaced with zero.",
        },
        "constraints": constraints,
    }


__all__ = [
    "InvalidSTEXOccupationCode",
    "synthesize_business_workforce_intelligence",
]
