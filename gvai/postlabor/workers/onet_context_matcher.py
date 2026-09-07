from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

from gvai.postlabor.sources.onet import (
    OnetClient,
    OnetWorkContext,
)


@dataclass(frozen=True)
class OnetContextMatch:
    source_code: str
    target_code: str
    context_similarity: float
    shared_context_count: int
    source_context_count: int
    target_context_count: int


def _context_vector(
    contexts: Iterable[OnetWorkContext],
) -> Dict[str, float]:
    return {
        context.element_id: float(context.context)
        for context in contexts
        if context.element_id
    }


def context_similarity(
    source: Iterable[OnetWorkContext],
    target: Iterable[OnetWorkContext],
) -> float:
    """
    Compare two occupations using standardized O*NET work-context
    profiles.

    100 means very similar job environments and conditions.
    0 means little measurable contextual overlap.
    """
    source_vector = _context_vector(source)
    target_vector = _context_vector(target)

    all_ids = set(source_vector) | set(target_vector)

    if not all_ids:
        return 0.0

    numerator = 0.0
    denominator = 0.0

    for element_id in all_ids:
        source_value = source_vector.get(element_id, 0.0)
        target_value = target_vector.get(element_id, 0.0)

        numerator += min(source_value, target_value)
        denominator += max(source_value, target_value)

    if denominator <= 0:
        return 0.0

    return round(
        (numerator / denominator) * 100.0,
        2,
    )


def compare_onet_work_context(
    source_code: str,
    target_code: str,
    *,
    client: OnetClient | None = None,
) -> OnetContextMatch:
    client = client or OnetClient()

    source = client.work_context(source_code)
    target = client.work_context(target_code)

    source_ids = {
        item.element_id
        for item in source
        if item.element_id
    }

    target_ids = {
        item.element_id
        for item in target
        if item.element_id
    }

    similarity = context_similarity(
        source,
        target,
    )

    return OnetContextMatch(
        source_code=source_code,
        target_code=target_code,
        context_similarity=similarity,
        shared_context_count=len(
            source_ids & target_ids
        ),
        source_context_count=len(source_ids),
        target_context_count=len(target_ids),
    )
