from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from gvai.postlabor.workers.occupation_market import (
    OccupationMarketRecord,
    demand_outlook_score,
    retraining_burden_score,
    wage_retention_score,
)


@dataclass(frozen=True)
class PrefilteredCandidate:
    record: OccupationMarketRecord
    preliminary_score: float
    demand_outlook: float
    wage_retention: float
    retraining_resilience: float


def prefilter_market_candidates(
    *,
    records: Iterable[OccupationMarketRecord],
    source_soc_code: str,
    current_annual_wage: Optional[float],
    limit: int = 40,
) -> List[PrefilteredCandidate]:
    """
    Cheap BLS-only candidate prefilter.

    This is not the final career recommendation score.

    It exists only to reduce the occupation universe before expensive
    O*NET skill and work-characteristic analysis.

    Uses:
      - projected demand
      - wage retention
      - retraining resilience

    No automation or skill-transfer assumptions are made here.
    """

    results: List[PrefilteredCandidate] = []

    for record in records:
        if record.soc_code == source_soc_code:
            continue

        demand = demand_outlook_score(record)

        wage = wage_retention_score(
            current_annual_wage=current_annual_wage,
            candidate_annual_wage=record.median_annual_wage,
        )

        retraining_resilience = (
            100.0 - retraining_burden_score(record)
        )

        preliminary_score = (
            demand * 0.45
            + wage * 0.30
            + retraining_resilience * 0.25
        )

        results.append(
            PrefilteredCandidate(
                record=record,
                preliminary_score=round(preliminary_score, 2),
                demand_outlook=demand,
                wage_retention=wage,
                retraining_resilience=round(
                    retraining_resilience,
                    2,
                ),
            )
        )

    results.sort(
        key=lambda item: (
            item.preliminary_score,
            item.demand_outlook,
        ),
        reverse=True,
    )

    return results[:max(1, limit)]
