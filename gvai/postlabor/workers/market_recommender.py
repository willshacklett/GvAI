from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from gvai.postlabor.workers.candidate_builder import (
    build_candidate_from_market,
)
from gvai.postlabor.workers.occupation_market import (
    OccupationMarketRecord,
)
from gvai.postlabor.workers.schema import (
    CareerCandidate,
    CurrentCareerAssessment,
    WorkerProfile,
)
from gvai.postlabor.workers.transition import (
    WorkerTransitionResult,
    analyze_worker_transition,
)


@dataclass(frozen=True)
class CandidateInputs:
    """
    Inputs not yet supplied directly by BLS.

    These will later come from:
    - O*NET skill similarity
    - automation exposure/task models
    - local job-market data
    """

    skill_transferability: float = 50.0
    automation_displacement_pressure: float = 50.0
    geographic_opportunity: float = 50.0
    confidence: float = 0.60


def build_market_candidates(
    *,
    candidate_records: Iterable[OccupationMarketRecord],
    current_annual_wage: Optional[float],
    inputs_by_soc: Optional[Dict[str, CandidateInputs]] = None,
) -> List[CareerCandidate]:

    inputs_by_soc = inputs_by_soc or {}

    candidates: List[CareerCandidate] = []

    for record in candidate_records:
        inputs = inputs_by_soc.get(
            record.soc_code,
            CandidateInputs(),
        )

        candidates.append(
            build_candidate_from_market(
                record=record,
                current_annual_wage=current_annual_wage,
                skill_transferability=inputs.skill_transferability,
                automation_displacement_pressure=(
                    inputs.automation_displacement_pressure
                ),
                geographic_opportunity=(
                    inputs.geographic_opportunity
                ),
                confidence=inputs.confidence,
                notes=(
                    "Demand, wage, and retraining inputs derived from "
                    "BLS occupational projections. Skill transferability, "
                    "automation pressure, and local opportunity remain "
                    "provisional until their live data sources are connected."
                ),
            )
        )

    return candidates


def recommend_market_transitions(
    *,
    worker: WorkerProfile,
    current_assessment: CurrentCareerAssessment,
    candidate_records: Iterable[OccupationMarketRecord],
    inputs_by_soc: Optional[Dict[str, CandidateInputs]] = None,
) -> WorkerTransitionResult:

    current_annual_wage = (
        worker.current_wage * 2080
        if worker.current_wage is not None
        else None
    )

    candidates = build_market_candidates(
        candidate_records=candidate_records,
        current_annual_wage=current_annual_wage,
        inputs_by_soc=inputs_by_soc,
    )

    return analyze_worker_transition(
        worker,
        current_assessment,
        candidates,
    )
