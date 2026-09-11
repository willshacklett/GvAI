from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .scoring import (
    STEX_RUBRIC_VERSION,
    calculate_task_exposure,
)


@dataclass(frozen=True)
class TaskRatingRecord:
    schema_version: str
    rubric_version: str

    occupation_code: str
    occupation_title: str

    task_id: str
    task_title: str
    task_category: str

    source_importance: float
    importance_status: str

    source_name: str
    source_year: int
    source_vintage_label: str

    digital_capability: float
    physical_execution: float
    human_presence_requirement: float
    augmentation_likelihood: float

    structural_exposure: float

    scorer_id: str
    scored_at_utc: str
    rationale: str

    @classmethod
    def create(
        cls,
        *,
        occupation_code: str,
        occupation_title: str,
        task_id: str,
        task_title: str,
        task_category: str,
        source_importance: float,
        source_name: str,
        source_year: int,
        digital_capability: float,
        physical_execution: float,
        human_presence_requirement: float,
        augmentation_likelihood: float,
        scorer_id: str,
        rationale: str,
        scored_at_utc: str | None = None,
    ) -> "TaskRatingRecord":
        if not rationale.strip():
            raise ValueError("rationale must not be empty")

        if not scorer_id.strip():
            raise ValueError("scorer_id must not be empty")

        augmentation = float(augmentation_likelihood)
        if augmentation < 0 or augmentation > 4:
            raise ValueError(
                "augmentation_likelihood must be between "
                f"0 and 4 inclusive; got {augmentation}"
            )

        category = task_category.strip()

        if float(source_importance) == 0.0 and category.lower() == "new":
            importance_status = "unrated"
        else:
            importance_status = "rated"

        if scored_at_utc is None:
            scored_at_utc = datetime.now(
                timezone.utc
            ).isoformat()

        exposure = calculate_task_exposure(
            digital_capability=digital_capability,
            physical_execution=physical_execution,
            human_presence_requirement=human_presence_requirement,
        )

        return cls(
            schema_version="gvai.stex.task-rating.v0.1",
            rubric_version=STEX_RUBRIC_VERSION,
            occupation_code=occupation_code,
            occupation_title=occupation_title,
            task_id=str(task_id),
            task_title=task_title,
            task_category=task_category,
            source_importance=float(source_importance),
            importance_status=importance_status,
            source_name=source_name,
            source_year=int(source_year),
            source_vintage_label=(
                f"{source_name} {int(source_year)}"
            ),
            digital_capability=float(digital_capability),
            physical_execution=float(physical_execution),
            human_presence_requirement=float(
                human_presence_requirement
            ),
            augmentation_likelihood=augmentation,
            structural_exposure=exposure,
            scorer_id=scorer_id,
            scored_at_utc=scored_at_utc,
            rationale=rationale,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
