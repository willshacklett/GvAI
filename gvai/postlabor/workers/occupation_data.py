from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OccupationSkill:
    skill_id: str
    name: str
    importance: Optional[float] = None
    description: str = ""


@dataclass(frozen=True)
class OccupationRecord:
    occupation_code: str
    title: str
    description: str = ""
    bright_outlook: Optional[bool] = None
    skills: List[OccupationSkill] = None

    def __post_init__(self):
        if self.skills is None:
            object.__setattr__(self, "skills", [])


def skill_vector(record: OccupationRecord) -> Dict[str, float]:
    """
    Convert an occupation's skill list into a comparable skill vector.

    Missing importance values are treated conservatively as 0.
    """
    return {
        skill.skill_id: float(skill.importance or 0.0)
        for skill in record.skills
    }


def skill_similarity(
    source: OccupationRecord,
    target: OccupationRecord,
) -> float:
    """
    Transparent first-pass skill similarity score from 0-100.

    Uses weighted overlap of O*NET skill importance values.
    Later this can be upgraded to include:
    - knowledge
    - work activities
    - abilities
    - technology skills
    - credentials
    - experience
    """

    source_vector = skill_vector(source)
    target_vector = skill_vector(target)

    all_skill_ids = set(source_vector) | set(target_vector)

    if not all_skill_ids:
        return 0.0

    overlap = 0.0
    maximum = 0.0

    for skill_id in all_skill_ids:
        source_value = source_vector.get(skill_id, 0.0)
        target_value = target_vector.get(skill_id, 0.0)

        overlap += min(source_value, target_value)
        maximum += max(source_value, target_value)

    if maximum == 0:
        return 0.0

    return round((overlap / maximum) * 100.0, 2)
