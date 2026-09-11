from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .records import TaskRatingRecord


@dataclass(frozen=True)
class OccupationSTEXResult:
    occupation_code: str
    occupation_title: str

    rated_task_count: int
    unrated_task_count: int

    total_importance_weight: float
    structural_exposure: float
    augmentation_likelihood: float

    rubric_version: str

    def to_dict(self) -> dict:
        return {
            "occupation_code": self.occupation_code,
            "occupation_title": self.occupation_title,
            "rated_task_count": self.rated_task_count,
            "unrated_task_count": self.unrated_task_count,
            "total_importance_weight": self.total_importance_weight,
            "structural_exposure": self.structural_exposure,
            "augmentation_likelihood": self.augmentation_likelihood,
            "rubric_version": self.rubric_version,
        }


def aggregate_occupation_stex(
    records: Iterable[TaskRatingRecord],
) -> OccupationSTEXResult:
    records = list(records)

    if not records:
        raise ValueError("at least one task rating record is required")

    occupation_codes = {r.occupation_code for r in records}
    occupation_titles = {r.occupation_title for r in records}
    rubric_versions = {r.rubric_version for r in records}

    if len(occupation_codes) != 1:
        raise ValueError(
            "all task records must belong to the same occupation"
        )

    if len(occupation_titles) != 1:
        raise ValueError(
            "all task records must use the same occupation title"
        )

    if len(rubric_versions) != 1:
        raise ValueError(
            "all task records must use the same rubric version"
        )

    rated = [
        r
        for r in records
        if r.importance_status == "rated"
        and r.source_importance > 0
    ]

    unrated = [
        r
        for r in records
        if r.importance_status != "rated"
        or r.source_importance <= 0
    ]

    if not rated:
        raise ValueError(
            "occupation has no rated tasks with positive importance"
        )

    total_weight = sum(r.source_importance for r in rated)

    structural = sum(
        r.structural_exposure * r.source_importance
        for r in rated
    ) / total_weight

    augmentation = sum(
        r.augmentation_likelihood * r.source_importance
        for r in rated
    ) / total_weight

    first = rated[0]

    return OccupationSTEXResult(
        occupation_code=first.occupation_code,
        occupation_title=first.occupation_title,
        rated_task_count=len(rated),
        unrated_task_count=len(unrated),
        total_importance_weight=round(total_weight, 4),
        structural_exposure=round(structural, 4),
        augmentation_likelihood=round(augmentation, 4),
        rubric_version=first.rubric_version,
    )
