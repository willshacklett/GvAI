from __future__ import annotations

from typing import Iterable

from gvai.postlabor.workers.schema import (
    CareerCandidate,
    CurrentCareerAssessment,
    WorkerProfile,
)
from gvai.postlabor.workers.transition import (
    WorkerTransitionResult,
    analyze_worker_transition,
)


def run_worker_transition(
    *,
    occupation: str,
    location: str,
    experience_years: float,
    current_assessment: CurrentCareerAssessment,
    candidates: Iterable[CareerCandidate],
    skills=None,
    education=None,
    licenses=None,
    current_wage=None,
    desired_wage=None,
    mobility_radius_miles=None,
) -> WorkerTransitionResult:
    """
    Public service boundary for Worker Transition Intelligence.

    API routes and future Carl tools should call this function instead of
    directly assembling the scoring engine themselves.
    """

    worker = WorkerProfile(
        occupation=occupation,
        location=location,
        experience_years=experience_years,
        skills=list(skills or []),
        education=education,
        licenses=list(licenses or []),
        current_wage=current_wage,
        desired_wage=desired_wage,
        mobility_radius_miles=mobility_radius_miles,
    )

    return analyze_worker_transition(
        worker,
        current_assessment,
        candidates,
    )
