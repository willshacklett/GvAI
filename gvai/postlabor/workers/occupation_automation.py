from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from gvai.postlabor.sources.bls_projections import (
    index_by_soc,
    load_occupational_projections,
)
from gvai.postlabor.sources.onet import OnetClient
from gvai.postlabor.workers.automation_exposure import (
    AutomationAssessment,
    index_ai_exposure,
    load_ai_exposure,
    assess_automation,
)
from gvai.postlabor.workers.onet_characteristics import (
    OccupationCharacteristics,
)
from gvai.postlabor.workers.onet_signals import (
    occupation_characteristics_from_onet,
)


DEFAULT_PROJECTIONS_PATH = Path(
    "data/bls/occupational_projections_2025_2035.xlsx"
)

DEFAULT_AI_EXPOSURE_PATH = Path(
    "data/bls/ai_exposure_categories.xlsx"
)


@dataclass(frozen=True)
class OccupationAutomationResult:
    onet_code: str
    soc_code: str
    title: str

    employment_change_percent: float
    median_annual_wage: Optional[float]
    ai_exposure_category: str

    characteristics: OccupationCharacteristics
    automation: AutomationAssessment

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def base_soc_code(occupation_code: str) -> str:
    """
    Convert an O*NET-SOC detailed code such as 37-2021.00
    to the base SOC code used by BLS: 37-2021.
    """
    return str(occupation_code).strip().split(".")[0]


def assess_occupation_automation(
    occupation_code: str,
    *,
    onet_client: Optional[OnetClient] = None,
    projections_path: Path | str = DEFAULT_PROJECTIONS_PATH,
    ai_exposure_path: Path | str = DEFAULT_AI_EXPOSURE_PATH,
) -> OccupationAutomationResult:
    """
    Universal occupation automation assessment.

    Combines:
      - O*NET work activities
      - O*NET work context
      - BLS employment projections
      - BLS relative AI exposure

    No occupation-specific scoring rules are used.
    """
    client = onet_client or OnetClient()

    characteristics = occupation_characteristics_from_onet(
        occupation_code,
        client=client,
    )

    soc_code = base_soc_code(occupation_code)

    projections = index_by_soc(
        load_occupational_projections(
            str(projections_path),
            sheet_name="Table 1.2",
        )
    )

    exposure_records = index_ai_exposure(
        load_ai_exposure(str(ai_exposure_path))
    )

    market = projections.get(soc_code)
    if market is None:
        raise LookupError(
            f"No BLS projection record found for SOC {soc_code}."
        )

    exposure = exposure_records.get(soc_code)
    if exposure is None:
        raise LookupError(
            f"No BLS AI exposure record found for SOC {soc_code}."
        )

    source_confidence = min(
        characteristics.confidence,
        0.95,
    )

    automation = assess_automation(
        exposure=exposure,
        employment_change_percent=market.employment_change_percent,
        physical_task_resilience=(
            characteristics.physical_task_resilience
        ),
        augmentation_potential=(
            characteristics.augmentation_potential
        ),
        confidence=source_confidence,
    )

    return OccupationAutomationResult(
        onet_code=occupation_code,
        soc_code=soc_code,
        title=characteristics.title,
        employment_change_percent=market.employment_change_percent,
        median_annual_wage=market.median_annual_wage,
        ai_exposure_category=exposure.category,
        characteristics=characteristics,
        automation=automation,
    )
