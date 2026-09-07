from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Dict, Iterable, List

from gvai.postlabor.workers.occupation_market import OccupationMarketRecord
from gvai.postlabor.workers.occupation_search import search_occupations


@dataclass(frozen=True)
class OccupationResolution:
    query: str
    soc_code: str
    title: str
    confidence: float
    match_type: str

    def to_dict(self):
        return asdict(self)


# Human-language aliases.
#
# These are not predictions or scores. They simply help translate ordinary
# job names into likely canonical occupation titles.
DEFAULT_ALIASES: Dict[str, List[str]] = {
    "warehouse worker": [
        "Stockers and order fillers",
        "Laborers and freight, stock, and material movers, hand",
    ],
    "warehouse associate": [
        "Stockers and order fillers",
        "Laborers and freight, stock, and material movers, hand",
    ],
    "forklift operator": [
        "Industrial truck and tractor operators",
    ],
    "pest tech": [
        "Pest control workers",
    ],
    "pest control technician": [
        "Pest control workers",
    ],
    "truck driver": [
        "Heavy and tractor-trailer truck drivers",
        "Light truck drivers",
    ],
    "bookkeeper": [
        "Bookkeeping, accounting, and auditing clerks",
    ],
    "cashier": [
        "Cashiers",
    ],
    "maintenance tech": [
        "Maintenance and repair workers, general",
    ],
    "maintenance technician": [
        "Maintenance and repair workers, general",
    ],
}


def _normalize(value: str) -> str:
    return " ".join(
        str(value or "")
        .lower()
        .replace("-", " ")
        .replace(",", " ")
        .split()
    )


def _title_index(
    records: Iterable[OccupationMarketRecord],
) -> Dict[str, OccupationMarketRecord]:
    return {
        _normalize(record.title): record
        for record in records
    }


def resolve_occupation(
    records: Iterable[OccupationMarketRecord],
    query: str,
    *,
    aliases: Dict[str, List[str]] | None = None,
    limit: int = 5,
    minimum_confidence: float = 0.60,
) -> List[OccupationResolution]:
    """
    Resolve ordinary job language into canonical BLS occupations.

    Resolution order:
    1. explicit human-language aliases
    2. exact canonical title
    3. BLS title search
    4. fuzzy title similarity

    The resolver returns candidates rather than silently forcing one answer.
    """

    records = list(records)
    aliases = aliases or DEFAULT_ALIASES

    normalized_query = _normalize(query)

    if not normalized_query:
        return []

    by_title = _title_index(records)

    results: List[OccupationResolution] = []
    seen = set()

    def add(
        record: OccupationMarketRecord,
        confidence: float,
        match_type: str,
    ) -> None:
        if record.soc_code in seen:
            return

        seen.add(record.soc_code)

        results.append(
            OccupationResolution(
                query=query,
                soc_code=record.soc_code,
                title=record.title,
                confidence=round(
                    max(0.0, min(1.0, confidence)),
                    4,
                ),
                match_type=match_type,
            )
        )

    # ------------------------------------------------------------------
    # Explicit aliases
    # ------------------------------------------------------------------
    alias_targets = aliases.get(normalized_query, [])

    for position, target_title in enumerate(alias_targets):
        record = by_title.get(
            _normalize(target_title)
        )

        if record is not None:
            confidence = 0.98 - (position * 0.04)

            add(
                record,
                confidence,
                "alias",
            )

    # ------------------------------------------------------------------
    # Exact canonical title
    # ------------------------------------------------------------------
    exact = by_title.get(normalized_query)

    if exact is not None:
        add(
            exact,
            1.0,
            "exact_title",
        )

    # ------------------------------------------------------------------
    # Existing transparent search engine
    # ------------------------------------------------------------------
    searched = search_occupations(
        records,
        query,
        limit=max(limit * 2, 10),
    )

    for position, record in enumerate(searched):
        confidence = max(
            0.55,
            0.90 - (position * 0.05),
        )

        add(
            record,
            confidence,
            "title_search",
        )

    # ------------------------------------------------------------------
    # Fuzzy fallback
    # ------------------------------------------------------------------
    fuzzy = []

    for record in records:
        similarity = SequenceMatcher(
            None,
            normalized_query,
            _normalize(record.title),
        ).ratio()

        if similarity >= 0.45:
            fuzzy.append(
                (
                    similarity,
                    record,
                )
            )

    fuzzy.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    for similarity, record in fuzzy[:limit]:
        add(
            record,
            similarity * 0.85,
            "fuzzy_title",
        )

    results.sort(
        key=lambda item: (
            item.confidence,
            item.title,
        ),
        reverse=True,
    )

    filtered = [
        item
        for item in results
        if item.confidence >= minimum_confidence
    ]

    return filtered[:limit]
