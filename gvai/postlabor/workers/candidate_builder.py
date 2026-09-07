from __future__ import annotations

from typing import Optional

from gvai.postlabor.workers.occupation_market import (
    OccupationMarketRecord,
    demand_outlook_score,
    retraining_burden_score,
    wage_retention_score,
)
from gvai.postlabor.workers.schema import CareerCandidate


def build_candidate_from_market(
    *,
    record: OccupationMarketRecord,
    current_annual_wage: Optional[float],
    skill_transferability: float,
    automation_displacement_pressure: float,
    geographic_opportunity: float = 50.0,
    confidence: float = 0.75,
    notes: str = "",
) -> CareerCandidate:
    """
    Build a Worker Transition candidate using real BLS market data
    for demand, wages, and retraining burden.

    Skill transferability, automation pressure, and geographic opportunity
    remain separate inputs until O*NET and local-job connectors are live.
    """

    return CareerCandidate(
        occupation=record.title,
        skill_transferability=skill_transferability,
        demand_outlook=demand_outlook_score(record),
        automation_displacement_pressure=automation_displacement_pressure,
        retraining_burden=retraining_burden_score(record),
        wage_retention=wage_retention_score(
            current_annual_wage=current_annual_wage,
            candidate_annual_wage=record.median_annual_wage,
        ),
        geographic_opportunity=geographic_opportunity,
        confidence=confidence,
        notes=notes,
    )
