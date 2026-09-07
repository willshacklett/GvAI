from __future__ import annotations

import re
from typing import Iterable, List, Optional

from gvai.postlabor.workers.occupation_market import OccupationMarketRecord


def _normalize(text: str) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9\s]", " ", str(text or "").lower()).split()
    )


def find_by_soc(
    records: Iterable[OccupationMarketRecord],
    soc_code: str,
) -> Optional[OccupationMarketRecord]:
    wanted = str(soc_code or "").strip()

    for record in records:
        if record.soc_code == wanted:
            return record

    return None


def search_occupations(
    records: Iterable[OccupationMarketRecord],
    query: str,
    *,
    limit: int = 20,
) -> List[OccupationMarketRecord]:
    """
    Simple transparent occupation-title search.

    Ranking priority:
    1. exact title match
    2. title starts with query
    3. phrase appears in title
    4. all query tokens appear
    5. partial token overlap
    """

    normalized_query = _normalize(query)

    if not normalized_query:
        return []

    query_tokens = set(normalized_query.split())

    scored = []

    for record in records:
        title = _normalize(record.title)
        title_tokens = set(title.split())

        if not title:
            continue

        if title == normalized_query:
            score = 1000

        elif title.startswith(normalized_query):
            score = 900

        elif normalized_query in title:
            score = 800

        else:
            overlap = len(query_tokens & title_tokens)

            if overlap == 0:
                continue

            if query_tokens.issubset(title_tokens):
                score = 700 + overlap
            else:
                score = 100 * (
                    overlap / max(len(query_tokens), 1)
                )

        scored.append(
            (
                score,
                record.title.lower(),
                record,
            )
        )

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1],
        )
    )

    return [
        item[2]
        for item in scored[:limit]
    ]
