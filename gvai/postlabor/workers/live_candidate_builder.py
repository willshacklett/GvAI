from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.workers.candidate_builder import (
    build_candidate_from_market,
)
from gvai.postlabor.workers.occupation_automation import (
    assess_occupation_automation,
)
from gvai.postlabor.workers.occupation_market import (
    OccupationMarketRecord,
)
from gvai.postlabor.workers.onet_matcher import (
    compare_onet_occupations,
)
from gvai.postlabor.workers.schema import CareerCandidate


@dataclass(frozen=True)
class LiveCandidateEvidence:
    source_onet_code: str
    target_onet_code: str
    skill_transferability: float
    automation_displacement_pressure: float
    automation_confidence: float


@dataclass(frozen=True)
class LiveCandidateResult:
    candidate: CareerCandidate
    evidence: LiveCandidateEvidence


def soc_to_onet_code(soc_code: str) -> str:
    code = str(soc_code or "").strip()
    return code if "." in code else f"{code}.00"


def build_live_candidate(
    *,
    source_onet_code: str,
    target_record: OccupationMarketRecord,
    current_annual_wage: Optional[float],
    geographic_opportunity: float = 50.0,
    client: OnetClient | None = None,
) -> LiveCandidateResult:
    """
    Build a transition candidate using live O*NET skill similarity
    plus BLS/O*NET automation assessment.

    Geographic opportunity remains provisional until a local labor
    market/job-posting source is connected.
    """
    client = client or OnetClient()

    target_onet_code = soc_to_onet_code(
        target_record.soc_code
    )

    skill_match = compare_onet_occupations(
        source_onet_code,
        target_onet_code,
        client=client,
    )

    automation = assess_occupation_automation(
        target_onet_code,
        onet_client=client,
    )

    candidate = build_candidate_from_market(
        record=target_record,
        current_annual_wage=current_annual_wage,
        skill_transferability=(
            skill_match.skill_transferability
        ),
        automation_displacement_pressure=(
            automation.automation.displacement_pressure
        ),
        geographic_opportunity=geographic_opportunity,
        confidence=min(
            automation.automation.confidence,
            0.90,
        ),
        notes=(
            "Demand, wage, and retraining inputs derived from BLS "
            "occupational projections. Skill transferability is derived "
            "from O*NET skill profiles. Automation pressure is derived "
            "from BLS AI exposure, BLS employment projections, and "
            "O*NET work characteristics. Geographic opportunity remains "
            "provisional."
        ),
    )

    return LiveCandidateResult(
        candidate=candidate,
        evidence=LiveCandidateEvidence(
            source_onet_code=source_onet_code,
            target_onet_code=target_onet_code,
            skill_transferability=(
                skill_match.skill_transferability
            ),
            automation_displacement_pressure=(
                automation.automation.displacement_pressure
            ),
            automation_confidence=(
                automation.automation.confidence
            ),
        ),
    )
