from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _validate_score(name: str, value: float) -> None:
    if not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be between 0 and 100")


@dataclass(frozen=True)
class WorkerProfile:
    """
    Human-facing worker profile used by Worker Transition Intelligence.

    This describes the person, not a labor-market prediction.
    """

    occupation: str
    location: str

    experience_years: float = 0.0
    skills: List[str] = field(default_factory=list)
    education: Optional[str] = None
    licenses: List[str] = field(default_factory=list)

    current_wage: Optional[float] = None
    desired_wage: Optional[float] = None

    remote_preference: Optional[str] = None
    mobility_radius_miles: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.occupation.strip():
            raise ValueError("occupation cannot be empty")

        if not self.location.strip():
            raise ValueError("location cannot be empty")

        if self.experience_years < 0:
            raise ValueError("experience_years cannot be negative")

        if self.current_wage is not None and self.current_wage < 0:
            raise ValueError("current_wage cannot be negative")

        if self.desired_wage is not None and self.desired_wage < 0:
            raise ValueError("desired_wage cannot be negative")

        if (
            self.mobility_radius_miles is not None
            and self.mobility_radius_miles < 0
        ):
            raise ValueError("mobility_radius_miles cannot be negative")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CurrentCareerAssessment:
    """
    Assessment of the worker's current occupation.

    All component inputs are expressed on 0-100 scales.
    """

    automation_displacement_pressure: float
    augmentation_potential: float
    demand_outlook: float
    confidence: float = 0.75

    def __post_init__(self) -> None:
        _validate_score(
            "automation_displacement_pressure",
            self.automation_displacement_pressure,
        )
        _validate_score(
            "augmentation_potential",
            self.augmentation_potential,
        )
        _validate_score(
            "demand_outlook",
            self.demand_outlook,
        )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CareerCandidate:
    """
    One possible destination occupation for a worker transition.

    The component scores will eventually be derived from:
    - O*NET skills and task similarity
    - BLS employment projections
    - automation exposure models
    - wage data
    - training/credential requirements
    - live geographic job openings
    """

    occupation: str

    skill_transferability: float
    demand_outlook: float
    automation_displacement_pressure: float
    retraining_burden: float
    wage_retention: float
    geographic_opportunity: float

    confidence: float = 0.75

    notes: str = ""

    def __post_init__(self) -> None:
        if not self.occupation.strip():
            raise ValueError("occupation cannot be empty")

        for name, value in (
            ("skill_transferability", self.skill_transferability),
            ("demand_outlook", self.demand_outlook),
            (
                "automation_displacement_pressure",
                self.automation_displacement_pressure,
            ),
            ("retraining_burden", self.retraining_burden),
            ("wage_retention", self.wage_retention),
            ("geographic_opportunity", self.geographic_opportunity),
        ):
            _validate_score(name, value)

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def automation_resilience(self) -> float:
        return round(
            100.0 - self.automation_displacement_pressure,
            2,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["automation_resilience"] = self.automation_resilience
        return data
