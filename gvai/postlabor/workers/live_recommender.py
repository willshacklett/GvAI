from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from requests import RequestException

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.workers.live_candidate_builder import (
    LiveCandidateResult,
    build_live_candidate,
)
from gvai.postlabor.workers.occupation_market import (
    OccupationMarketRecord,
)
from gvai.postlabor.workers.transition import (
    TransitionOpportunity,
    score_transition_candidate,
)


@dataclass(frozen=True)
class RankedLiveCandidate:
    rank: int
    transition_score: float
    opportunity: TransitionOpportunity
    result: LiveCandidateResult


def rank_live_candidates(
    *,
    source_onet_code: str,
    candidate_records: Iterable[OccupationMarketRecord],
    current_annual_wage: Optional[float],
    geographic_opportunity: float = 50.0,
    client: OnetClient | None = None,
    limit: int = 10,
) -> List[RankedLiveCandidate]:
    """
    Rank candidate occupations using:
    - live O*NET skill similarity
    - BLS occupational projections
    - BLS relative AI exposure
    - O*NET work characteristics
    - transition scoring

    Geographic opportunity remains provisional.
    """
    client = client or OnetClient()

    scored_results = []

    for record in candidate_records:
        try:
            live = build_live_candidate(
                source_onet_code=source_onet_code,
                target_record=record,
                current_annual_wage=current_annual_wage,
                geographic_opportunity=geographic_opportunity,
                client=client,
            )

            opportunity = score_transition_candidate(
                live.candidate
            )

            scored_results.append(
                (
                    opportunity.score,
                    opportunity.confidence,
                    opportunity,
                    live,
                )
            )

        except (LookupError, ValueError, RequestException):
            # Some broad SOC/BLS records may not have a directly
            # compatible O*NET detailed occupation or complete source data.
            # Skip them rather than fabricating a recommendation.
            continue

    scored_results.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return [
        RankedLiveCandidate(
            rank=index + 1,
            transition_score=round(score, 2),
            opportunity=opportunity,
            result=live,
        )
        for index, (
            score,
            _confidence,
            opportunity,
            live,
        ) in enumerate(scored_results[:limit])
    ]
