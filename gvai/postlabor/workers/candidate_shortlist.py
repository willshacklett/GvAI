from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from requests import RequestException

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.workers.candidate_prefilter import (
    PrefilteredCandidate,
    prefilter_market_candidates,
)
from gvai.postlabor.workers.occupation_market import (
    OccupationMarketRecord,
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
    skill_data_available: bool
    shortlist_score: float


def shortlist_candidates(
    *,
    source_onet_code: str,
    records: Iterable[OccupationMarketRecord],
    current_annual_wage: Optional[float],
    client: OnetClient | None = None,
    prefilter_limit: int = 40,
    shortlist_limit: int = 15,
) -> List[SkillShortlistedCandidate]:
    """
    Stage-two career discovery.

    1. Use cheap BLS market data to create a broad pool.
    2. Use O*NET skill similarity to remove economically attractive
       but implausible career jumps.
    3. Leave expensive automation/work-context analysis for finalists.

    No occupation-specific rules are used.
    """
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

        # This is only a shortlist score, not the final transition score.
        #
        # Keep enough market weight that a worker is not trapped inside
        # their existing career family, while using skill similarity to
        # eliminate clearly implausible jumps.
        shortlist_score = (
            item.preliminary_score * 0.55
            + skill_score * 0.45
        )

        results.append(
            SkillShortlistedCandidate(
                record=item.record,
                preliminary_score=item.preliminary_score,
                skill_transferability=round(
                    skill_score,
                    2,
                ),
                skill_data_available=skill_data_available,
                shortlist_score=round(
                    shortlist_score,
                    2,
                ),
            )
        )

    results.sort(
        key=lambda item: (
            item.shortlist_score,
            item.skill_data_available,
            item.preliminary_score,
        ),
        reverse=True,
    )

    return results[:max(1, shortlist_limit)]
