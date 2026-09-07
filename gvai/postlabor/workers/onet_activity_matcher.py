from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

from gvai.postlabor.sources.onet import (
    OnetClient,
    OnetWorkActivity,
)


@dataclass(frozen=True)
class OnetActivityMatch:
    source_code: str
    target_code: str
    activity_similarity: float
    shared_activity_count: int
    source_activity_count: int
    target_activity_count: int


def _activity_vector(
    activities: Iterable[OnetWorkActivity],
) -> Dict[str, float]:
    return {
        activity.element_id: float(activity.importance)
        for activity in activities
        if activity.element_id
    }


def activity_similarity(
    source: Iterable[OnetWorkActivity],
    target: Iterable[OnetWorkActivity],
) -> float:
    """
    Compare two occupations using standardized O*NET work-activity
    importance profiles.

    Uses weighted min/max similarity across shared O*NET element IDs.

    100 = nearly identical activity profile.
    0 = no meaningful overlap.
    """
    source_vector = _activity_vector(source)
    target_vector = _activity_vector(target)

    all_ids = set(source_vector) | set(target_vector)

    if not all_ids:
        return 0.0

    numerator = 0.0
    denominator = 0.0

    for element_id in all_ids:
        source_value = source_vector.get(element_id, 0.0)
        target_value = target_vector.get(element_id, 0.0)

        numerator += min(source_value, target_value)
        denominator += max(source_value, target_value)

    if denominator <= 0:
        return 0.0

    return round(
        (numerator / denominator) * 100.0,
        2,
    )


def compare_onet_work_activities(
    source_code: str,
    target_code: str,
    *,
    client: OnetClient | None = None,
) -> OnetActivityMatch:
    client = client or OnetClient()

    source = client.work_activities(source_code)
    target = client.work_activities(target_code)

    source_ids = {
        activity.element_id
        for activity in source
        if activity.element_id
    }

    target_ids = {
        activity.element_id
        for activity in target
        if activity.element_id
    }

    similarity = activity_similarity(
        source,
        target,
    )

    return OnetActivityMatch(
        source_code=source_code,
        target_code=target_code,
        activity_similarity=similarity,
        shared_activity_count=len(
            source_ids & target_ids
        ),
        source_activity_count=len(source_ids),
        target_activity_count=len(target_ids),
    )
