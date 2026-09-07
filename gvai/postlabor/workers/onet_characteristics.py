from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OccupationCharacteristics:
    occupation_code: str
    title: str

    physical_task_resilience: float
    augmentation_potential: float
    routine_intensity: float
    interpersonal_intensity: float
    information_intensity: float

    confidence: float
    evidence: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def derive_characteristics(
    *,
    occupation_code: str,
    title: str,
    physical_activity: float,
    worksite_presence: float,
    task_variability: float,
    interpersonal_activity: float,
    information_processing: float,
    routine_activity: float,
    confidence: float = 0.75,
) -> OccupationCharacteristics:
    """
    Universal occupation-characteristics model.

    All inputs are normalized 0-100 signals derived from O*NET work context,
    generalized work activities, tasks, and related descriptors.

    This function contains no occupation-specific rules.
    """

    physical_activity = clamp(physical_activity)
    worksite_presence = clamp(worksite_presence)
    task_variability = clamp(task_variability)
    interpersonal_activity = clamp(interpersonal_activity)
    information_processing = clamp(information_processing)
    routine_activity = clamp(routine_activity)

    physical_task_resilience = (
        physical_activity * 0.40
        + worksite_presence * 0.35
        + task_variability * 0.25
    )

    # Augmentation tends to be higher when AI can assist information work,
    # judgment, communication, and variable problem-solving without fully
    # substituting for physical or interpersonal execution.
    augmentation_potential = (
        information_processing * 0.35
        + interpersonal_activity * 0.20
        + task_variability * 0.25
        + (100.0 - routine_activity) * 0.20
    )

    evidence = [
        f"Physical activity signal: {physical_activity:.1f}/100.",
        f"Worksite presence signal: {worksite_presence:.1f}/100.",
        f"Task variability signal: {task_variability:.1f}/100.",
        f"Interpersonal activity signal: {interpersonal_activity:.1f}/100.",
        f"Information-processing signal: {information_processing:.1f}/100.",
        f"Routine activity signal: {routine_activity:.1f}/100.",
        (
            "Physical-task resilience is higher where work requires embodied "
            "activity, location-specific execution, and variable conditions."
        ),
        (
            "Augmentation potential is higher where AI can assist information, "
            "judgment, communication, and variable problem-solving tasks."
        ),
    ]

    return OccupationCharacteristics(
        occupation_code=occupation_code,
        title=title,
        physical_task_resilience=round(physical_task_resilience, 2),
        augmentation_potential=round(augmentation_potential, 2),
        routine_intensity=round(routine_activity, 2),
        interpersonal_intensity=round(interpersonal_activity, 2),
        information_intensity=round(information_processing, 2),
        confidence=round(max(0.0, min(1.0, confidence)), 4),
        evidence=evidence,
    )
