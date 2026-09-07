from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

from gvai.postlabor.sources.onet import (
    OnetClient,
    OnetKnowledge,
)


@dataclass(frozen=True)
class OnetKnowledgeMatch:
    source_code: str
    target_code: str
    knowledge_similarity: float
    shared_knowledge_count: int
    source_knowledge_count: int
    target_knowledge_count: int


def _knowledge_vector(
    knowledge: Iterable[OnetKnowledge],
) -> Dict[str, float]:
    return {
        item.element_id: float(item.importance)
        for item in knowledge
        if item.element_id
    }


def knowledge_similarity(
    source: Iterable[OnetKnowledge],
    target: Iterable[OnetKnowledge],
) -> float:
    source_vector = _knowledge_vector(source)
    target_vector = _knowledge_vector(target)

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


def compare_onet_knowledge(
    source_code: str,
    target_code: str,
    *,
    client: OnetClient | None = None,
) -> OnetKnowledgeMatch:
    client = client or OnetClient()

    source = client.knowledge(source_code)
    target = client.knowledge(target_code)

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

    similarity = knowledge_similarity(
        source,
        target,
    )

    return OnetKnowledgeMatch(
        source_code=source_code,
        target_code=target_code,
        knowledge_similarity=similarity,
        shared_knowledge_count=len(
            source_ids & target_ids
        ),
        source_knowledge_count=len(source_ids),
        target_knowledge_count=len(target_ids),
    )
