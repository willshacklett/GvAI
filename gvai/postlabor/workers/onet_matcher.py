from __future__ import annotations

from dataclasses import dataclass
from typing import List

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.workers.occupation_data import (
    OccupationRecord,
    skill_similarity,
)


@dataclass(frozen=True)
class OnetSkillMatch:
    source_code: str
    source_title: str
    target_code: str
    target_title: str
    skill_transferability: float
    source_skill_count: int
    target_skill_count: int

    def to_dict(self):
        return {
            "source_code": self.source_code,
            "source_title": self.source_title,
            "target_code": self.target_code,
            "target_title": self.target_title,
            "skill_transferability": self.skill_transferability,
            "source_skill_count": self.source_skill_count,
            "target_skill_count": self.target_skill_count,
        }


def compare_onet_occupations(
    source_code: str,
    target_code: str,
    *,
    client: OnetClient | None = None,
) -> OnetSkillMatch:
    """
    Compare two occupations using live O*NET skill importance profiles.
    """

    client = client or OnetClient()

    source: OccupationRecord = client.occupation_with_skills(source_code)
    target: OccupationRecord = client.occupation_with_skills(target_code)

    similarity = skill_similarity(source, target)

    return OnetSkillMatch(
        source_code=source.occupation_code,
        source_title=source.title,
        target_code=target.occupation_code,
        target_title=target.title,
        skill_transferability=similarity,
        source_skill_count=len(source.skills),
        target_skill_count=len(target.skills),
    )
