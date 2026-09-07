from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from requests import RequestException

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.workers.candidate_prefilter import (
    prefilter_market_candidates,
)
from gvai.postlabor.workers.occupation_market import (
    OccupationMarketRecord,
)
from gvai.postlabor.workers.onet_activity_matcher import (
    compare_onet_work_activities,
)
from gvai.postlabor.workers.onet_context_matcher import (
    compare_onet_work_context,
)
from gvai.postlabor.workers.onet_matcher import (
    compare_onet_occupations,
)
from gvai.postlabor.workers.worker_assessment import (
    onet_code_from_soc,
)


@dataclass(frozen=True)
class SkillShortlistedCandidate:
    record: OccupationMarketRecord
    preliminary_score: float

    skill_transferability: float
    activity_similarity: float
    context_similarity: float

    skill_data_available: bool
    activity_data_available: bool
    context_data_available: bool

    career_adjacency: float
    shortlist_score: float


def career_adjacency_score(
    *,
    skill_transferability: float,
    activity_similarity: float,
    context_similarity: float,
) -> float:
    """
    Universal v0.1 occupation adjacency score.

    Measures similarity using:
    - O*NET skills
    - O*NET work activities
    - O*NET work context
    """

    score = (
        skill_transferability * 0.35
        + activity_similarity * 0.35
        + context_similarity * 0.30
    )

    return round(
        max(0.0, min(100.0, score)),
        2,
    )


def shortlist_candidates(
    *,
    source_onet_code: str,
    records: Iterable[OccupationMarketRecord],
    current_annual_wage: Optional[float],
    client: OnetClient | None = None,
    prefilter_limit: int = 40,
    shortlist_limit: int = 15,
) -> List[SkillShortlistedCandidate]:

    client = client or OnetClient()

    source_soc_code = (
        str(source_onet_code).strip().split(".")[0]
    )

    prefiltered = prefilter_market_candidates(
        records=records,
        source_soc_code=source_soc_code,
        current_annual_wage=current_annual_wage,
        limit=prefilter_limit,
    )

    results: List[SkillShortlistedCandidate] = []

    for item in prefiltered:
        target_onet_code = onet_code_from_soc(
            item.record.soc_code
        )

        try:
            match = compare_onet_occupations(
                source_onet_code,
                target_onet_code,
                client=client,
            )

            skill_data_available = (
                match.source_skill_count > 0
                and match.target_skill_count > 0
            )

            skill_score = (
                match.skill_transferability
                if skill_data_available
                else 50.0
            )

        except (LookupError, ValueError, RequestException):
            skill_data_available = False
            skill_score = 50.0

        try:
            match = compare_onet_work_activities(
                source_onet_code,
                target_onet_code,
                client=client,
            )

            activity_data_available = (
                match.source_activity_count > 0
                and match.target_activity_count > 0
            )

            activity_score = (
                match.activity_similarity
                if activity_data_available
                else 50.0
            )

        except (LookupError, ValueError, RequestException):
            activity_data_available = False
            activity_score = 50.0

        try:
            match = compare_onet_work_context(
                source_onet_code,
                target_onet_code,
                client=client,
            )

            context_data_available = (
                match.source_context_count > 0
                and match.target_context_count > 0
            )

            context_score = (
                match.context_similarity
                if context_data_available
                else 50.0
            )

        except (LookupError, ValueError, RequestException):
            context_data_available = False
            context_score = 50.0

        adjacency = career_adjacency_score(
            skill_transferability=skill_score,
            activity_similarity=activity_score,
            context_similarity=context_score,
        )

        shortlist_score = (
            adjacency * 0.55
            + item.preliminary_score * 0.45
        )

        results.append(
            SkillShortlistedCandidate(
                record=item.record,
                preliminary_score=item.preliminary_score,
                skill_transferability=round(skill_score, 2),
                activity_similarity=round(activity_score, 2),
                context_similarity=round(context_score, 2),
                skill_data_available=skill_data_available,
                activity_data_available=activity_data_available,
                context_data_available=context_data_available,
                career_adjacency=adjacency,
                shortlist_score=round(shortlist_score, 2),
            )
        )

    results.sort(
        key=lambda item: (
            item.shortlist_score,
            item.career_adjacency,
            item.preliminary_score,
        ),
        reverse=True,
    )

    return results[:max(1, shortlist_limit)]
