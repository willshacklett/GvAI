from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.workers.candidate_prefilter import (
    prefilter_market_candidates,
)
from gvai.postlabor.workers.occupation_market import (
    OccupationMarketRecord,
)


@dataclass(frozen=True)
class CandidatePoolItem:
    record: OccupationMarketRecord
    from_onet_related: bool
    from_market_prefilter: bool
    bright_outlook: bool


def build_candidate_pool(
    *,
    source_onet_code: str,
    records: Iterable[OccupationMarketRecord],
    current_annual_wage: Optional[float],
    client: OnetClient | None = None,
    market_limit: int = 40,
) -> List[CandidatePoolItem]:
    """
    Universal candidate generation.

    Combines:
    - O*NET related occupations for natural adjacency
    - BLS market prefilter for opportunity/reinvention paths

    Final ranking happens later.
    """
    client = client or OnetClient()

    records = list(records)

    by_soc: Dict[str, OccupationMarketRecord] = {
        record.soc_code: record
        for record in records
    }

    source_soc = str(source_onet_code).split(".")[0]

    combined: Dict[str, CandidatePoolItem] = {}

    # ----------------------------------------------------------
    # O*NET related occupations
    # ----------------------------------------------------------
    for related in client.related_occupations(
        source_onet_code,
        start=1,
        end=50,
    ):
        soc = related.occupation_code.split(".")[0]

        if soc == source_soc:
            continue

        record = by_soc.get(soc)
        if record is None:
            continue

        combined[soc] = CandidatePoolItem(
            record=record,
            from_onet_related=True,
            from_market_prefilter=False,
            bright_outlook=related.bright_outlook,
        )

    # ----------------------------------------------------------
    # BLS market opportunity candidates
    # ----------------------------------------------------------
    market = prefilter_market_candidates(
        records=records,
        source_soc_code=source_soc,
        current_annual_wage=current_annual_wage,
        limit=market_limit,
    )

    for item in market:
        soc = item.record.soc_code

        existing = combined.get(soc)

        if existing is not None:
            combined[soc] = CandidatePoolItem(
                record=existing.record,
                from_onet_related=True,
                from_market_prefilter=True,
                bright_outlook=existing.bright_outlook,
            )
        else:
            combined[soc] = CandidatePoolItem(
                record=item.record,
                from_onet_related=False,
                from_market_prefilter=True,
                bright_outlook=False,
            )

    return list(combined.values())
