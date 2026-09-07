from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from gvai.postlabor.sources.bls_projections import (
    load_occupational_projections,
)
from gvai.postlabor.workers.occupation_automation import (
    OccupationAutomationResult,
    assess_occupation_automation,
)
from gvai.postlabor.workers.occupation_resolver import (
    OccupationResolution,
    resolve_occupation,
)


DEFAULT_PROJECTIONS_PATH = Path(
    "data/bls/occupational_projections_2025_2035.xlsx"
)


@dataclass(frozen=True)
class WorkerOccupationResolution:
    query: str
    candidates: List[OccupationResolution]

    @property
    def resolved(self) -> bool:
        return len(self.candidates) == 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "resolved": self.resolved,
            "candidates": [
                candidate.to_dict()
                for candidate in self.candidates
            ],
        }


@dataclass(frozen=True)
class WorkerOccupationAssessment:
    query: str
    resolution: OccupationResolution
    automation: OccupationAutomationResult

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def onet_code_from_soc(soc_code: str) -> str:
    """
    Convert a base detailed SOC code such as 37-2021
    to the standard O*NET-SOC form 37-2021.00.

    This is the normal first lookup form. Future crosswalk support
    can handle occupations with more specialized O*NET extensions.
    """
    code = str(soc_code or "").strip()

    if "." in code:
        return code

    return f"{code}.00"


def resolve_worker_occupation(
    query: str,
    *,
    projections_path: Path | str = DEFAULT_PROJECTIONS_PATH,
    limit: int = 5,
) -> WorkerOccupationResolution:
    """
    Resolve ordinary job language into candidate BLS occupations.

    This function intentionally does not silently choose among multiple
    plausible occupations.
    """
    records = load_occupational_projections(
        str(projections_path),
        sheet_name="Table 1.2",
    )

    candidates = resolve_occupation(
        records,
        query,
        limit=limit,
    )

    return WorkerOccupationResolution(
        query=query,
        candidates=candidates,
    )


def assess_resolved_occupation(
    resolution: OccupationResolution,
    *,
    query: str | None = None,
) -> WorkerOccupationAssessment:
    """
    Run the universal automation assessment after an occupation has
    been selected or confirmed.
    """
    onet_code = onet_code_from_soc(
        resolution.soc_code
    )

    result = assess_occupation_automation(
        onet_code
    )

    return WorkerOccupationAssessment(
        query=query or resolution.query,
        resolution=resolution,
        automation=result,
    )
