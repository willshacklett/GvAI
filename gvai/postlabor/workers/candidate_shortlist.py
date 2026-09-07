from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from requests import RequestException

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.workers.candidate_pool import (
    build_candidate_pool,
)
from gvai.postlabor.workers.occupation_market import (
    OccupationMarketRecord,
    demand_outlook_score,
    retraining_burden_score,
    wage_retention_score,
)
from gvai.postlabor.workers.onet_activity_matcher import (
    compare_onet_work_activities,
)
from gvai.postlabor.workers.onet_context_matcher import (
    compare_onet_work_context,
)
from gvai.postlabor.workers.onet_knowledge_matcher import (
    compare_onet_knowledge,
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
    knowledge_similarity: float

    skill_data_available: bool
    activity_data_available: bool
    context_data_available: bool
    knowledge_data_available: bool

    from_onet_related: bool
    from_market_prefilter: bool
    bright_outlook: bool

    career_adjacency: float
    shortlist_score: float


def career_adjacency_score(
    *,
    skill_transferability: float,
    activity_similarity: float,
    context_similarity: float,
    knowledge_similarity: float,
) -> float:
    """
    Universal career adjacency v0.2.

    30% transferable skills
    30% work activities
    20% work context
    20% domain knowledge
    """
    score = (
        skill_transferability * 0.30
        + activity_similarity * 0.30
        + context_similarity * 0.20
        + knowledge_similarity * 0.20
    )

    return round(
        max(0.0, min(100.0, score)),
        2,
    )


def _market_score(
    *,
    record: OccupationMarketRecord,
    current_annual_wage: Optional[float],
) -> float:
    """
    Same transparent market logic used by the BLS prefilter,
    calculated for every merged-pool occupation.
    """
    demand = demand_outlook_score(record)

    wage = wage_retention_score(
        current_annual_wage=current_annual_wage,
        candidate_annual_wage=record.median_annual_wage,
    )

    retraining_resilience = (
        100.0 - retraining_burden_score(record)
    )

    return round(
        demand * 0.45
        + wage * 0.30
        + retraining_resilience * 0.25,
        2,
    )


def shortlist_candidates(
    *,
    source_onet_code: str,
    records: Iterable[OccupationMarketRecord],
    current_annual_wage: Optional[float],
    client: OnetClient | None = None,
    market_limit: int = 40,
    shortlist_limit: int = 15,
) -> List[SkillShortlistedCandidate]:
    """
    Universal staged candidate shortlist.

    Candidate generation:
      - O*NET related occupations
      - BLS high-opportunity occupations

    Candidate evaluation:
      - skills
      - work activities
      - work context
      - knowledge
      - BLS market opportunity

    Full automation/displacement analysis happens later.
    """
    client = client or OnetClient()

    records = list(records)

    pool = build_candidate_pool(
        source_onet_code=source_onet_code,
        records=records,
        current_annual_wage=current_annual_wage,
        client=client,
        market_limit=market_limit,
    )

    results: List[SkillShortlistedCandidate] = []

    for pool_item in pool:
        record = pool_item.record

        target_onet_code = onet_code_from_soc(
            record.soc_code
        )

        market_score = _market_score(
            record=record,
            current_annual_wage=current_annual_wage,
        )

        # ------------------------------------------------------
        # Skills
        # ------------------------------------------------------
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

        # ------------------------------------------------------
        # Work activities
        # ------------------------------------------------------
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

        # ------------------------------------------------------
        # Work context
        # ------------------------------------------------------
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

        # ------------------------------------------------------
        # Knowledge
        # ------------------------------------------------------
        try:
            match = compare_onet_knowledge(
                source_onet_code,
                target_onet_code,
                client=client,
            )

            knowledge_data_available = (
                match.source_knowledge_count > 0
                and match.target_knowledge_count > 0
            )

            knowledge_score = (
                match.knowledge_similarity
                if knowledge_data_available
                else 50.0
            )

        except (LookupError, ValueError, RequestException):
            knowledge_data_available = False
            knowledge_score = 50.0

        adjacency = career_adjacency_score(
            skill_transferability=skill_score,
            activity_similarity=activity_score,
            context_similarity=context_score,
            knowledge_similarity=knowledge_score,
        )

        shortlist_score = (
            adjacency * 0.55
            + market_score * 0.45
        )

        results.append(
            SkillShortlistedCandidate(
                record=record,
                preliminary_score=market_score,

                skill_transferability=round(skill_score, 2),
                activity_similarity=round(activity_score, 2),
                context_similarity=round(context_score, 2),
                knowledge_similarity=round(knowledge_score, 2),

                skill_data_available=skill_data_available,
                activity_data_available=activity_data_available,
                context_data_available=context_data_available,
                knowledge_data_available=knowledge_data_available,

                from_onet_related=pool_item.from_onet_related,
                from_market_prefilter=pool_item.from_market_prefilter,
                bright_outlook=pool_item.bright_outlook,

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
