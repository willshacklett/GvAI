"""
Worker Personal Comparison V1.

Connects a self-reported Worker Profile to a single occupation the
worker is investigating and answers: "What facts about my situation
are relevant to this occupation?"

This module presents two kinds of facts side by side and never
converts either into a judgment:

  A. self-reported Worker Profile facts (claim_source
     "self_reported_worker_profile", never independently verified)
  B. published O*NET / BLS occupational and regional evidence

It intentionally does NOT compute or return:
  - a match, fit, qualification, or transferability score
  - a skill/credential/education similarity or gap
  - a recommendation or ranking
  - a confidence value
  - fuzzy/embeddings/LLM-based semantic matching of any kind

The Worker Profile's saved current occupation is always the source
occupation. Investigating another occupation never overwrites it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from gvai.postlabor.region_labor_intelligence import (
    DEFAULT_STEX_SOURCE_YEAR,
    synthesize_region_labor_intelligence,
)
from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.stex.store import (
    InvalidSTEXOccupationCode,
    normalize_occupation_code,
)
from gvai.postlabor.worker_region_outlook import _occupation_regional_wage_signal

logger = logging.getLogger(__name__)

# Fixed, non-secret upstream hostname for safe diagnostic logging only.
ONET_UPSTREAM_HOST = "api-v2.onetcenter.org"

# Deterministic count of target-occupation O*NET skills shown as reference
# facts (sorted by importance desc, then name, then id). This is a display
# limit only -- never a similarity ranking against worker-reported skills.
TARGET_SKILLS_DISPLAY_COUNT = 5

STATUS_BOTH_REPORTED = "both_reported"
STATUS_WORKER_ONLY = "worker_only"
STATUS_EVIDENCE_ONLY = "evidence_only"
STATUS_NEITHER_REPORTED = "neither_reported"


def _log_failure(signal_name: str, occupation_code: str, exc: Exception) -> None:
    status_code = None
    response = getattr(exc, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", None)

    # Safe diagnostic only: no keys, headers, URLs, or worker data are logged.
    logger.warning(
        "O*NET %s request failed "
        "(exception_class=%s, upstream_host=%s, "
        "occupation_code=%s, upstream_status_code=%s)",
        signal_name,
        type(exc).__name__,
        ONET_UPSTREAM_HOST,
        occupation_code,
        status_code,
    )


def _overall_status(worker_status: str, evidence_status: str) -> str:
    worker_known = worker_status == "known"
    evidence_known = evidence_status in ("known", "suppressed")
    if worker_known and evidence_known:
        return STATUS_BOTH_REPORTED
    if worker_known:
        return STATUS_WORKER_ONLY
    if evidence_known:
        return STATUS_EVIDENCE_ONLY
    return STATUS_NEITHER_REPORTED


def _comparison(
    comparison_id: str,
    title: str,
    *,
    worker_fact: Dict[str, Any],
    occupational_evidence: Optional[Dict[str, Any]],
    explanation: str,
    source: str,
    limitation: Optional[str],
) -> Dict[str, Any]:
    evidence = occupational_evidence or {"status": "unavailable"}
    return {
        "comparison_id": comparison_id,
        "title": title,
        "status": _overall_status(worker_fact.get("status"), evidence.get("status")),
        "worker_fact": worker_fact,
        "occupational_evidence": occupational_evidence,
        "explanation": explanation,
        "source": source,
        "limitation": limitation,
    }


def _target_job_zone_signal(client: OnetClient, occupation_code: str) -> Dict[str, Any]:
    try:
        job_zone = client.job_zone(occupation_code)
    except Exception as exc:  # noqa: BLE001 - fall back to "unavailable"
        _log_failure("job_zone", occupation_code, exc)
        return {
            "status": "unavailable",
            "job_zone_code": None,
            "title": None,
            "education": None,
            "related_experience": None,
            "job_training": None,
            "explanation": "O*NET Job Zone data is unavailable for this occupation.",
        }

    return {
        "status": "known",
        "job_zone_code": job_zone.code,
        "title": job_zone.title,
        "education": job_zone.education,
        "related_experience": job_zone.related_experience,
        "job_training": job_zone.job_training,
        "explanation": (
            "O*NET Job Zone describes the overall level of preparation "
            "typically associated with this occupation."
        ),
    }


def _target_education_signal(client: OnetClient, occupation_code: str) -> Dict[str, Any]:
    try:
        levels = client.education(occupation_code)
    except Exception as exc:  # noqa: BLE001 - fall back to "unavailable"
        _log_failure("education", occupation_code, exc)
        return {
            "status": "unavailable",
            "levels": [],
            "explanation": "O*NET education survey data is unavailable for this occupation.",
        }

    return {
        "status": "known",
        "levels": [
            {
                "code": level.code,
                "title": level.title,
                "percentage_of_respondents": level.percentage_of_respondents,
            }
            for level in levels
        ],
        "explanation": (
            "O*NET survey respondents currently working in this occupation "
            "reported the percentage who hold each education level. This "
            "describes the occupation's current workforce, not a "
            "requirement for any individual."
        ),
    }


def _target_skills_signal(client: OnetClient, occupation_code: str) -> Dict[str, Any]:
    try:
        items = client.skills(occupation_code)
    except Exception as exc:  # noqa: BLE001 - fall back to "unavailable"
        _log_failure("skills", occupation_code, exc)
        return {
            "status": "unavailable",
            "items": [],
            "explanation": "O*NET skill data is unavailable for this occupation.",
        }

    known = [item for item in items if item.importance is not None]
    known.sort(key=lambda item: (-item.importance, item.name, item.skill_id))

    return {
        "status": "known",
        "items": [
            {
                "id": item.skill_id,
                "name": item.name,
                "description": item.description,
                "importance": item.importance,
            }
            for item in known[:TARGET_SKILLS_DISPLAY_COUNT]
        ],
        "explanation": (
            "These are the O*NET skill elements with the highest published "
            "importance for this occupation. GVAI has not determined that "
            "these are matches or gaps relative to your reported skills."
        ),
    }


def _wage_comparison(
    wage: Dict[str, Any],
    oews_area_code: Optional[str],
    target_code: str,
    wage_year: int,
) -> Dict[str, Any]:
    minimum_annual = wage.get("minimum_annual")
    minimum_hourly = wage.get("minimum_hourly")
    worker_known = minimum_annual is not None or minimum_hourly is not None
    worker_fact = {
        "status": "known" if worker_known else "not_provided",
        "minimum_annual": minimum_annual,
        "minimum_hourly": minimum_hourly,
    }

    occupational_evidence = _occupation_regional_wage_signal(
        oews_area_code, target_code, wage_year=wage_year
    )

    limitation = "A published median wage is not a prediction of your pay."
    if occupational_evidence.get("match_specificity") == "broader_category":
        limitation = occupational_evidence["explanation"]

    return _comparison(
        "wage",
        "Pay",
        worker_fact=worker_fact,
        occupational_evidence=occupational_evidence,
        explanation=(
            "Your self-reported minimum desired wage is shown beside "
            "published regional wage evidence for the occupation being "
            "investigated."
        ),
        source=occupational_evidence.get("source") or "BLS OEWS",
        limitation=limitation,
    )


def _mobility_comparison(mobility: Dict[str, Any]) -> Dict[str, Any]:
    radius_miles = mobility.get("radius_miles")
    willing_to_relocate = mobility.get("willing_to_relocate")
    remote_preference = mobility.get("remote_preference")
    worker_known = (
        radius_miles is not None
        or willing_to_relocate is not None
        or remote_preference is not None
    )
    worker_fact = {
        "status": "known" if worker_known else "not_provided",
        "radius_miles": radius_miles,
        "willing_to_relocate": willing_to_relocate,
        "remote_preference": remote_preference,
    }

    occupational_evidence = {
        "status": "unavailable",
        "explanation": (
            "GVAI does not have geographic distance or remote-availability "
            "evidence for this occupation, so it cannot determine commuting "
            "feasibility or remote suitability."
        ),
    }

    return _comparison(
        "mobility",
        "Mobility & Remote Preferences",
        worker_fact=worker_fact,
        occupational_evidence=occupational_evidence,
        explanation=(
            "Your self-reported mobility radius, relocation willingness, "
            "and remote-work preference are presented as personal "
            "constraints, not as feasibility for this occupation."
        ),
        source="Worker-provided information",
        limitation=(
            "The presence of regional data does not mean this occupation "
            "is within range, and GVAI does not infer remote availability."
        ),
    )


def _education_comparison(
    education: Dict[str, Any],
    job_zone_signal: Dict[str, Any],
    education_signal: Dict[str, Any],
) -> Dict[str, Any]:
    highest_level = education.get("highest_level")
    worker_fact = {
        "status": "known" if highest_level is not None else "not_provided",
        "highest_level": highest_level,
    }

    occupational_evidence = {
        "status": (
            "known"
            if job_zone_signal["status"] == "known"
            or education_signal["status"] == "known"
            else "unavailable"
        ),
        "job_zone": job_zone_signal,
        "education_survey": education_signal,
    }

    return _comparison(
        "education",
        "Preparation",
        worker_fact=worker_fact,
        occupational_evidence=occupational_evidence,
        explanation=(
            "Your self-reported highest education level is shown beside "
            "O*NET's published Job Zone and education-survey evidence for "
            "the occupation being investigated. Because your entry is "
            "free text, these facts are presented side by side rather than "
            "as an equality match."
        ),
        source="O*NET Web Services",
        limitation=(
            "This is not proof of qualification or a requirement match."
        ),
    )


def _credentials_comparison(credentials: List[str]) -> Dict[str, Any]:
    worker_fact = {
        "status": "known" if credentials else "not_provided",
        "items": list(credentials),
    }

    occupational_evidence = {
        "status": "unavailable",
        "explanation": (
            "GVAI does not currently have authoritative occupation-specific "
            "licensing or certification requirements, so it cannot "
            "determine whether these credentials satisfy this occupation's "
            "requirements. Verify applicable state and local requirements "
            "independently."
        ),
    }

    return _comparison(
        "credentials",
        "Credentials",
        worker_fact=worker_fact,
        occupational_evidence=occupational_evidence,
        explanation=(
            "Credentials you entered are shown as self-reported facts only."
        ),
        source="Worker-provided information",
        limitation=(
            "GVAI does not verify credentials or determine whether they "
            "satisfy target occupation licensing requirements."
        ),
    )


def _skills_comparison(
    skills: List[str],
    skills_signal: Dict[str, Any],
) -> Dict[str, Any]:
    worker_fact = {
        "status": "known" if skills else "not_provided",
        "items": list(skills),
    }

    return _comparison(
        "skills",
        "Skills",
        worker_fact=worker_fact,
        occupational_evidence=skills_signal,
        explanation=(
            "Skills you reported are free-text labels. O*NET skills are "
            "standardized occupational elements. These are shown as two "
            "separate factual lists."
        ),
        source="O*NET Web Services",
        limitation=(
            "GVAI has not determined that these are matches or gaps. No "
            "automatic skill matching, similarity scoring, or "
            "transferability inference is performed."
        ),
    )


def _experience_comparison(
    experience: Dict[str, Any],
    job_zone_signal: Dict[str, Any],
) -> Dict[str, Any]:
    years_in_current_occupation = experience.get("years_in_current_occupation")
    total_years_work_experience = experience.get("total_years_work_experience")
    worker_known = (
        years_in_current_occupation is not None
        or total_years_work_experience is not None
    )
    worker_fact = {
        "status": "known" if worker_known else "not_provided",
        "years_in_current_occupation": years_in_current_occupation,
        "total_years_work_experience": total_years_work_experience,
    }

    occupational_evidence = {
        "status": job_zone_signal["status"],
        "related_experience": job_zone_signal.get("related_experience"),
        "explanation": job_zone_signal["explanation"],
    }

    return _comparison(
        "experience",
        "Experience",
        worker_fact=worker_fact,
        occupational_evidence=occupational_evidence,
        explanation=(
            "Your self-reported years of experience are shown beside "
            "O*NET's related-experience text for the occupation being "
            "investigated."
        ),
        source="O*NET Web Services",
        limitation="This does not convert years of experience into a qualification.",
    )


def synthesize_worker_personal_comparison(
    profile: Dict[str, Any],
    target_occupation_code: str,
    *,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    onet_client: Optional[OnetClient] = None,
    target_occupation_title: Optional[str] = None,
    acs_year: int = 2024,
    stex_year: int = DEFAULT_STEX_SOURCE_YEAR,
) -> Dict[str, Any]:
    """
    Compare a validated, self-reported Worker Profile with published
    occupational and regional evidence for one investigated occupation.

    `profile` must already be normalized by
    `gvai.postlabor.worker_profile.validate_worker_profile`. This
    function never persists, logs, or forwards profile contents to an
    LLM or unrelated third-party service; only occupation and region
    identifiers are sent to O*NET/BLS evidence calls.

    Raises InvalidSTEXOccupationCode if target_occupation_code is not
    a valid O*NET-SOC code. Raises ValueError if only one of
    latitude/longitude is provided.
    """
    if not isinstance(profile, dict):
        raise ValueError("profile must be a validated Worker Profile mapping.")
    if (latitude is None) != (longitude is None):
        raise ValueError("latitude and longitude must be provided together.")

    target_code = normalize_occupation_code(target_occupation_code)

    source_occupation = profile.get("current_occupation") or {}
    source_code = source_occupation.get("occupation_code")
    source_title = source_occupation.get("occupation_title")

    client = onet_client or OnetClient()

    job_zone_signal = _target_job_zone_signal(client, target_code)
    education_signal = _target_education_signal(client, target_code)
    skills_signal = _target_skills_signal(client, target_code)

    oews_area_code = None
    if latitude is not None and longitude is not None:
        region = synthesize_region_labor_intelligence(
            latitude, longitude, acs_year=acs_year, stex_year=stex_year
        )
        if region.get("supported"):
            oews_area_code = region.get("oews_area_code")

    comparisons = [
        _wage_comparison(profile.get("wage") or {}, oews_area_code, target_code, stex_year),
        _mobility_comparison(profile.get("mobility") or {}),
        _education_comparison(profile.get("education") or {}, job_zone_signal, education_signal),
        _credentials_comparison(profile.get("credentials") or []),
        _skills_comparison(profile.get("skills") or [], skills_signal),
        _experience_comparison(profile.get("experience") or {}, job_zone_signal),
    ]

    return {
        "supported": True,
        "claim_source": "self_reported_worker_profile",
        "source_occupation": {
            "occupation_code": source_code,
            "occupation_title": source_title,
        },
        "target_occupation": {
            "occupation_code": target_code,
            "occupation_title": target_occupation_title or target_code,
        },
        "source_equals_target": bool(source_code) and source_code == target_code,
        "comparisons": comparisons,
        "explanation": (
            "This presents your self-reported Worker Profile facts beside "
            "published occupational and regional evidence for the "
            "occupation being investigated. It is not a match score, "
            "qualification judgment, or recommendation."
        ),
    }


__all__ = [
    "InvalidSTEXOccupationCode",
    "synthesize_worker_personal_comparison",
]
