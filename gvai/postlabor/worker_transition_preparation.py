"""
Factual O*NET preparation evidence for a source/current occupation and a
target/investigated occupation.

This module reports what O*NET's Job Zone and Education survey data say
about the typical preparation associated with each occupation. It is
evidence about occupations, not a judgment about any individual worker.

It intentionally does not:
  - compute a preparation-gap score
  - compute a readiness/qualification score
  - claim an individual has or lacks the typical preparation
  - label a transition easy or hard
  - invent state licensing/credential requirements (O*NET does not
    publish these through the endpoints this module reads, so this
    module reports none)

Job Zone education/experience/training text and O*NET's education
survey distribution are O*NET source values, reported unmodified.
Unavailable data remains unavailable -- it is never replaced with a
zero, an average, or another placeholder.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from requests import HTTPError, RequestException

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.stex.store import (
    InvalidSTEXOccupationCode,
    normalize_occupation_code,
)

logger = logging.getLogger(__name__)

# Fixed, non-secret upstream hostname for safe diagnostic logging only.
ONET_UPSTREAM_HOST = "api-v2.onetcenter.org"


def _job_zone_signal(
    client: OnetClient,
    occupation_code: str,
) -> Dict[str, Any]:
    try:
        job_zone = client.job_zone(occupation_code)
    except (RuntimeError, RequestException, ValueError, LookupError) as exc:
        _log_failure("job_zone", occupation_code, exc)
        return {
            "status": "unavailable",
            "job_zone_code": None,
            "title": None,
            "education": None,
            "related_experience": None,
            "job_training": None,
            "job_zone_examples": None,
            "svp_range": None,
            "explanation": (
                "O*NET Job Zone data is unavailable for this occupation."
            ),
        }

    return {
        "status": "known",
        "job_zone_code": job_zone.code,
        "title": job_zone.title,
        "education": job_zone.education,
        "related_experience": job_zone.related_experience,
        "job_training": job_zone.job_training,
        "job_zone_examples": job_zone.job_zone_examples,
        "svp_range": job_zone.svp_range,
        "explanation": (
            "O*NET Job Zone describes the overall level of preparation "
            "typically needed for this occupation, based on required "
            "education, related experience, and on-the-job training."
        ),
    }


def _education_signal(
    client: OnetClient,
    occupation_code: str,
) -> Dict[str, Any]:
    try:
        levels = client.education(occupation_code)
    except (RuntimeError, RequestException, ValueError, LookupError) as exc:
        _log_failure("education", occupation_code, exc)
        return {
            "status": "unavailable",
            "levels": [],
            "explanation": (
                "O*NET education survey data is unavailable for this "
                "occupation."
            ),
        }

    return {
        "status": "known",
        "levels": [
            {
                "code": level.code,
                "title": level.title,
                "percentage_of_respondents": (
                    level.percentage_of_respondents
                ),
            }
            for level in levels
        ],
        "explanation": (
            "O*NET survey respondents currently working in this "
            "occupation reported the percentage who hold each "
            "education level. This describes the occupation's "
            "current workforce, not a requirement for any individual."
        ),
    }


def _log_failure(
    signal_name: str,
    occupation_code: str,
    exc: Exception,
) -> None:
    status_code = None
    if isinstance(exc, HTTPError) and exc.response is not None:
        status_code = exc.response.status_code

    # Safe diagnostic only: no keys, headers, or URLs are ever logged.
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


def _occupation_preparation_evidence(
    client: OnetClient,
    occupation_code: str,
) -> Dict[str, Any]:
    job_zone = _job_zone_signal(client, occupation_code)
    education = _education_signal(client, occupation_code)

    return {
        "occupation_code": occupation_code,
        "job_zone": job_zone,
        "education": education,
    }


def synthesize_worker_transition_preparation_evidence(
    source_occupation_code: str,
    target_occupation_code: str,
    *,
    onet_client: Optional[OnetClient] = None,
    source_occupation_title: Optional[str] = None,
    target_occupation_title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Report O*NET Job Zone and education-survey evidence separately for
    a source (current) occupation and a target (investigated)
    occupation.

    This is descriptive occupational evidence only. It never compares
    the two occupations into a single preparation-gap value and never
    states whether a specific worker meets or lacks this preparation.

    Raises InvalidSTEXOccupationCode if either occupation_code is not
    a valid O*NET-SOC code.
    """
    source_code = normalize_occupation_code(source_occupation_code)
    target_code = normalize_occupation_code(target_occupation_code)

    client = onet_client or OnetClient()

    source_evidence = _occupation_preparation_evidence(client, source_code)
    target_evidence = _occupation_preparation_evidence(client, target_code)

    constraints = []
    for evidence in (source_evidence, target_evidence):
        for signal in (evidence["job_zone"], evidence["education"]):
            if signal["status"] == "unavailable":
                constraints.append(
                    f"{evidence['occupation_code']}: "
                    f"{signal['explanation']}"
                )

    return {
        "supported": True,
        "source_occupation_code": source_code,
        "source_occupation_title": source_occupation_title or source_code,
        "target_occupation_code": target_code,
        "target_occupation_title": target_occupation_title or target_code,
        "source_attribution": {
            "name": "O*NET Web Services",
            "note": (
                "Job Zone and education survey values are sourced "
                "directly from O*NET. GVAI does not modify these "
                "values or compute a preparation-gap score."
            ),
        },
        "source_preparation": source_evidence,
        "target_preparation": target_evidence,
        "explanation": (
            "This describes O*NET's published preparation profile for "
            "each occupation. It does not state whether any individual "
            "worker already has this preparation, and it is not a "
            "measure of how easy or hard a transition would be."
        ),
        "constraints": constraints,
    }


__all__ = [
    "InvalidSTEXOccupationCode",
    "synthesize_worker_transition_preparation_evidence",
]
