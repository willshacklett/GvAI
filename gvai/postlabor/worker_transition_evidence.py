"""
Factual O*NET occupation-to-occupation comparison for career transitions.

This module compares two O*NET occupations (a source/current occupation
and a target/investigated occupation) using existing live O*NET work
activity and skill importance ratings.

This is evidence, NOT a recommendation or a score. It intentionally
does not:
  - compute a similarity percentage
  - compute a transferability score
  - compute a qualification score
  - compute a retraining-burden score
  - produce a recommendation or composite score
  - rank occupations

Presence or absence of an O*NET skill/work-activity element describes
the occupation's O*NET profile only. It is never interpreted as a
worker's personal skill gap or qualification.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from requests import HTTPError, RequestException

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.stex.store import (
    InvalidSTEXOccupationCode,
    normalize_occupation_code,
)

logger = logging.getLogger(__name__)

# Fixed, non-secret upstream hostname for safe diagnostic logging only.
ONET_UPSTREAM_HOST = "api-v2.onetcenter.org"

# O*NET importance values are rescaled onto a 0-100 scale. A difference
# smaller than this threshold is presented as "similar emphasis" rather
# than as more-emphasized-in-either-occupation. This threshold only
# affects presentation grouping -- the raw source/target importance
# values are always returned unmodified.
TRANSITION_EVIDENCE_MATERIALITY_THRESHOLD = 5.0

EMPHASIS_MORE_IN_TARGET = "more_emphasized_in_target"
EMPHASIS_SIMILAR = "similar_emphasis"
EMPHASIS_MORE_IN_SOURCE = "more_emphasized_in_source"


def _classify_emphasis(
    difference: float,
    *,
    threshold: float = TRANSITION_EVIDENCE_MATERIALITY_THRESHOLD,
) -> str:
    if difference > threshold:
        return EMPHASIS_MORE_IN_TARGET
    if difference < -threshold:
        return EMPHASIS_MORE_IN_SOURCE
    return EMPHASIS_SIMILAR


def _normalize_skill(item: Any) -> Dict[str, Any]:
    return {
        "id": item.skill_id,
        "name": item.name,
        "description": item.description,
        "importance": item.importance,
    }


def _normalize_activity(item: Any) -> Dict[str, Any]:
    return {
        "id": item.element_id,
        "name": item.name,
        "description": item.description,
        "importance": item.importance,
    }


def _compare_elements(
    source_items: List[Dict[str, Any]],
    target_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compare matching elements between two occupations.

    Only elements present in both occupations' O*NET profile (matched
    by O*NET element id) with a known importance value on both sides
    are included. Ordering is deterministic: descending absolute
    importance difference, then name, then id.
    """
    source_map = {item["id"]: item for item in source_items if item["id"]}
    target_map = {item["id"]: item for item in target_items if item["id"]}

    common_ids = set(source_map) & set(target_map)

    results = []
    for element_id in common_ids:
        source = source_map[element_id]
        target = target_map[element_id]

        source_importance = source["importance"]
        target_importance = target["importance"]

        if source_importance is None or target_importance is None:
            continue

        difference = target_importance - source_importance

        results.append({
            "id": element_id,
            "name": source["name"] or target["name"],
            "description": source["description"] or target["description"],
            "source_importance": source_importance,
            "target_importance": target_importance,
            "importance_difference": difference,
            "emphasis": _classify_emphasis(difference),
        })

    results.sort(
        key=lambda item: (
            -abs(item["importance_difference"]),
            item["name"],
            item["id"],
        )
    )
    return results


def _build_comparison_signal(
    *,
    fetch: Callable[[str], List[Any]],
    normalize: Callable[[Any], Dict[str, Any]],
    source_code: str,
    target_code: str,
    signal_name: str,
) -> Dict[str, Any]:
    try:
        source_items = [normalize(item) for item in fetch(source_code)]
        target_items = [normalize(item) for item in fetch(target_code)]
    except (RuntimeError, RequestException, ValueError, LookupError) as exc:
        status_code = None
        if isinstance(exc, HTTPError) and exc.response is not None:
            status_code = exc.response.status_code

        # Safe diagnostic only: no keys, headers, or URLs are ever logged.
        logger.warning(
            "O*NET %s comparison request failed "
            "(exception_class=%s, upstream_host=%s, "
            "source_code=%s, target_code=%s, upstream_status_code=%s)",
            signal_name,
            type(exc).__name__,
            ONET_UPSTREAM_HOST,
            source_code,
            target_code,
            status_code,
        )

        return {
            "status": "unavailable",
            "items": [],
            "explanation": (
                f"O*NET {signal_name} data is unavailable for one or "
                "both occupations, so this comparison cannot be shown."
            ),
        }

    items = _compare_elements(source_items, target_items)

    return {
        "status": "known",
        "items": items,
        "explanation": (
            f"Matched O*NET {signal_name} elements are ordered by "
            "absolute importance difference within this occupation "
            "pair only. GVAI does not rank occupations."
        ),
    }


def synthesize_worker_transition_evidence(
    source_occupation_code: str,
    target_occupation_code: str,
    *,
    onet_client: OnetClient | None = None,
    source_occupation_title: str | None = None,
    target_occupation_title: str | None = None,
) -> Dict[str, Any]:
    """
    Deterministically compare O*NET work activities and skills between
    a source (current) occupation and a target (investigated)
    occupation.

    Raises InvalidSTEXOccupationCode if either occupation_code is not
    a valid O*NET-SOC code.
    """
    source_code = normalize_occupation_code(source_occupation_code)
    target_code = normalize_occupation_code(target_occupation_code)

    client = onet_client or OnetClient()

    work_activity_comparison = _build_comparison_signal(
        fetch=client.work_activities,
        normalize=_normalize_activity,
        source_code=source_code,
        target_code=target_code,
        signal_name="work activity",
    )
    skill_comparison = _build_comparison_signal(
        fetch=client.skills,
        normalize=_normalize_skill,
        source_code=source_code,
        target_code=target_code,
        signal_name="skill",
    )

    constraints = []
    for signal in (work_activity_comparison, skill_comparison):
        if signal["status"] == "unavailable":
            constraints.append(signal["explanation"])

    return {
        "supported": True,
        "source_occupation_code": source_code,
        "source_occupation_title": source_occupation_title or source_code,
        "target_occupation_code": target_code,
        "target_occupation_title": target_occupation_title or target_code,
        "source_attribution": {
            "name": "O*NET Web Services",
            "note": (
                "Work activity and skill importance ratings are "
                "sourced directly from O*NET. GVAI does not modify "
                "these values."
            ),
        },
        "materiality_threshold": TRANSITION_EVIDENCE_MATERIALITY_THRESHOLD,
        "work_activity_comparison": work_activity_comparison,
        "skill_comparison": skill_comparison,
        "explanation": (
            "GVAI compares O*NET occupational profiles. This does not "
            "determine whether an individual is qualified for a job "
            "or personally possesses or lacks a skill."
        ),
        "constraints": constraints,
    }


__all__ = [
    "InvalidSTEXOccupationCode",
    "TRANSITION_EVIDENCE_MATERIALITY_THRESHOLD",
    "synthesize_worker_transition_evidence",
]
