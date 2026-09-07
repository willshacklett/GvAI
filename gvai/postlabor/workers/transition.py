from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List

from gvai.postlabor.workers.schema import (
    CareerCandidate,
    CurrentCareerAssessment,
    WorkerProfile,
)


@dataclass(frozen=True)
class CareerResilienceResult:
    score: float
    confidence: float
    risk_band: str
    transition_urgency: float
    explanation: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TransitionOpportunity:
    occupation: str
    score: float
    confidence: float

    skill_transferability: float
    demand_outlook: float
    automation_resilience: float
    retraining_burden: float
    wage_retention: float
    geographic_opportunity: float

    recommendation: str
    explanation: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkerTransitionResult:
    worker: WorkerProfile
    current_career: CareerResilienceResult
    opportunities: List[TransitionOpportunity]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker": self.worker.to_dict(),
            "current_career": self.current_career.to_dict(),
            "opportunities": [
                opportunity.to_dict()
                for opportunity in self.opportunities
            ],
        }


CURRENT_CAREER_WEIGHTS = {
    "automation_resilience": 0.45,
    "augmentation_potential": 0.20,
    "demand_outlook": 0.35,
}


TRANSITION_WEIGHTS = {
    "skill_transferability": 0.25,
    "demand_outlook": 0.20,
    "automation_resilience": 0.20,
    "wage_retention": 0.15,
    "geographic_opportunity": 0.10,
    "retraining_resilience": 0.10,
}


def _risk_band(score: float) -> str:
    if score >= 75:
        return "high_resilience"
    if score >= 55:
        return "moderate_resilience"
    if score >= 35:
        return "elevated_transition_risk"
    return "high_transition_risk"


def _recommendation(score: float) -> str:
    if score >= 80:
        return "strong_transition_candidate"
    if score >= 65:
        return "good_transition_candidate"
    if score >= 50:
        return "possible_transition_candidate"
    return "weak_transition_candidate"


def score_current_career(
    assessment: CurrentCareerAssessment,
) -> CareerResilienceResult:

    automation_resilience = (
        100.0 - assessment.automation_displacement_pressure
    )

    score = (
        automation_resilience
        * CURRENT_CAREER_WEIGHTS["automation_resilience"]
        + assessment.augmentation_potential
        * CURRENT_CAREER_WEIGHTS["augmentation_potential"]
        + assessment.demand_outlook
        * CURRENT_CAREER_WEIGHTS["demand_outlook"]
    )

    # Urgency rises with displacement pressure and weak demand,
    # but falls where augmentation potential remains strong.
    transition_urgency = (
        assessment.automation_displacement_pressure * 0.55
        + (100.0 - assessment.demand_outlook) * 0.30
        + (100.0 - assessment.augmentation_potential) * 0.15
    )

    explanation = [
        (
            "Automation displacement pressure: "
            f"{assessment.automation_displacement_pressure:.1f}/100."
        ),
        (
            "AI/automation augmentation potential: "
            f"{assessment.augmentation_potential:.1f}/100."
        ),
        (
            "Occupation demand outlook: "
            f"{assessment.demand_outlook:.1f}/100."
        ),
        (
            "Transition urgency reflects displacement pressure, "
            "weak demand, and limited augmentation potential."
        ),
    ]

    return CareerResilienceResult(
        score=round(score, 2),
        confidence=round(assessment.confidence, 4),
        risk_band=_risk_band(score),
        transition_urgency=round(transition_urgency, 2),
        explanation=explanation,
    )


def score_transition_candidate(
    candidate: CareerCandidate,
) -> TransitionOpportunity:

    retraining_resilience = 100.0 - candidate.retraining_burden

    score = (
        candidate.skill_transferability
        * TRANSITION_WEIGHTS["skill_transferability"]
        + candidate.demand_outlook
        * TRANSITION_WEIGHTS["demand_outlook"]
        + candidate.automation_resilience
        * TRANSITION_WEIGHTS["automation_resilience"]
        + candidate.wage_retention
        * TRANSITION_WEIGHTS["wage_retention"]
        + candidate.geographic_opportunity
        * TRANSITION_WEIGHTS["geographic_opportunity"]
        + retraining_resilience
        * TRANSITION_WEIGHTS["retraining_resilience"]
    )

    explanation = [
        (
            f"Skill transferability "
            f"{candidate.skill_transferability:.1f}/100."
        ),
        (
            f"Future demand "
            f"{candidate.demand_outlook:.1f}/100."
        ),
        (
            f"Automation resilience "
            f"{candidate.automation_resilience:.1f}/100."
        ),
        (
            f"Wage retention "
            f"{candidate.wage_retention:.1f}/100."
        ),
        (
            f"Geographic opportunity "
            f"{candidate.geographic_opportunity:.1f}/100."
        ),
        (
            f"Retraining burden "
            f"{candidate.retraining_burden:.1f}/100 "
            f"(lower is better)."
        ),
    ]

    return TransitionOpportunity(
        occupation=candidate.occupation,
        score=round(score, 2),
        confidence=round(candidate.confidence, 4),
        skill_transferability=candidate.skill_transferability,
        demand_outlook=candidate.demand_outlook,
        automation_resilience=candidate.automation_resilience,
        retraining_burden=candidate.retraining_burden,
        wage_retention=candidate.wage_retention,
        geographic_opportunity=candidate.geographic_opportunity,
        recommendation=_recommendation(score),
        explanation=explanation,
    )


def analyze_worker_transition(
    worker: WorkerProfile,
    current_assessment: CurrentCareerAssessment,
    candidates: Iterable[CareerCandidate],
) -> WorkerTransitionResult:

    current_result = score_current_career(current_assessment)

    opportunities = [
        score_transition_candidate(candidate)
        for candidate in candidates
    ]

    opportunities.sort(
        key=lambda item: (
            item.score,
            item.confidence,
        ),
        reverse=True,
    )

    return WorkerTransitionResult(
        worker=worker,
        current_career=current_result,
        opportunities=opportunities,
    )
