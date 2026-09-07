from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.workers.candidate_shortlist import (
    SkillShortlistedCandidate,
    shortlist_candidates,
)
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
class TransitionRecommendation:
    rank: int
    transition_score: float

    shortlist: SkillShortlistedCandidate
    live: LiveCandidateResult
    opportunity: TransitionOpportunity

    path_type: str


def _path_type(
    candidate: SkillShortlistedCandidate,
) -> str:
    if (
        candidate.from_onet_related
        and candidate.from_market_prefilter
    ):
        return "strong_on_both"

    if candidate.from_onet_related:
        return "natural_next_step"

    return "high_opportunity_pivot"


def recommend_transitions(
    *,
    source_onet_code: str,
    records: Iterable[OccupationMarketRecord],
    current_annual_wage: Optional[float],
    client: OnetClient | None = None,
    market_limit: int = 40,
    shortlist_limit: int = 20,
    final_limit: int = 10,
) -> List[TransitionRecommendation]:
    """
    Full worker transition pipeline.

    1. Generate a merged O*NET + BLS occupation pool.
    2. Rank by career adjacency + market opportunity.
    3. Run full automation analysis on finalists.
    4. Rank by transition opportunity.
    """
    client = client or OnetClient()

    shortlist = shortlist_candidates(
        source_onet_code=source_onet_code,
        records=records,
        current_annual_wage=current_annual_wage,
        client=client,
        market_limit=market_limit,
        shortlist_limit=shortlist_limit,
    )

    ranked = []

    for candidate in shortlist:
        try:
            live = build_live_candidate(
                source_onet_code=source_onet_code,
                target_record=candidate.record,
                current_annual_wage=current_annual_wage,
                geographic_opportunity=50.0,
                client=client,
            )

            opportunity = score_transition_candidate(
                live.candidate,
                transferability_override=(
                    candidate.career_adjacency
                ),
            )

            ranked.append(
                (
                    opportunity.score,
                    opportunity.confidence,
                    candidate,
                    live,
                    opportunity,
                )
            )

        except (LookupError, ValueError):
            continue

    ranked.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return [
        TransitionRecommendation(
            rank=index + 1,
            transition_score=round(score, 2),
            shortlist=candidate,
            live=live,
            opportunity=opportunity,
            path_type=_path_type(candidate),
        )
        for index, (
            score,
            _confidence,
            candidate,
            live,
            opportunity,
        ) in enumerate(ranked[:final_limit])
    ]
