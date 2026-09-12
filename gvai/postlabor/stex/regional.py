from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Optional

from gvai.postlabor.sources.oews import (
    OEWS_ALL_OCCUPATIONS,
    OEWSEmploymentEstimate,
    normalize_soc_code,
)


@dataclass(frozen=True)
class RegionalSTEXOccupation:
    occupation_code: str
    employment: float
    structural_exposure: float

    @property
    def weighted_exposure(self) -> float:
        return (
            self.employment
            * self.structural_exposure
        )


@dataclass(frozen=True)
class RegionalSTEXResult:
    covered_employment: float
    reference_employment: float
    coverage_rate: float
    structural_exposure: float
    occupation_count: int

    def to_dict(self):
        return {
            "covered_employment":
                self.covered_employment,
            "reference_employment":
                self.reference_employment,
            "coverage_rate":
                self.coverage_rate,
            "structural_exposure":
                self.structural_exposure,
            "occupation_count":
                self.occupation_count,
        }


@dataclass(frozen=True)
class RegionalSTEXCoveragePlan:
    area_code: str
    source_year: int
    total_employment: float
    covered_employment: float
    coverage_rate: float
    covered_stex: float
    contributing_audited_occupations: tuple[dict[str, Any], ...]
    recommended_unaudited_occupations: tuple[dict[str, Any], ...]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "area_code": self.area_code,
            "source_year": self.source_year,
            "total_employment": self.total_employment,
            "stex_covered_employment": self.covered_employment,
            "coverage_percentage": self.coverage_rate,
            "covered_occupation_stex": self.covered_stex,
            "contributing_audited_occupations": [
                dict(item)
                for item in self.contributing_audited_occupations
            ],
            "recommended_unaudited_occupations": [
                dict(item)
                for item in self.recommended_unaudited_occupations
            ],
            "source": self.source,
        }


def aggregate_regional_stex(
    occupations:
        Iterable[RegionalSTEXOccupation],
    *,
    reference_employment: float,
) -> RegionalSTEXResult:
    """
    Employment-weight audited occupation STEX values.

    The returned structural_exposure is calculated only
    over occupations with audited STEX values supplied to
    this function.

    coverage_rate reports how much of the external
    reference employment denominator is represented by
    those occupations.

    This prevents incomplete STEX coverage from silently
    being presented as a complete regional estimate.
    """
    rows: List[
        RegionalSTEXOccupation
    ] = list(occupations)

    reference = float(
        reference_employment
    )

    if reference <= 0:
        raise ValueError(
            "reference_employment must be positive."
        )

    for row in rows:
        if row.employment < 0:
            raise ValueError(
                "Occupation employment cannot be negative."
            )

        if not (
            0
            <= row.structural_exposure
            <= 100
        ):
            raise ValueError(
                "Structural exposure must be between "
                "0 and 100."
            )

    covered = sum(
        row.employment
        for row in rows
        if row.employment > 0
    )

    if covered > reference:
        raise ValueError(
            "Covered employment cannot exceed "
            "reference employment."
        )

    if covered == 0:
        exposure = 0.0
    else:
        exposure = (
            sum(
                row.weighted_exposure
                for row in rows
            )
            / covered
        )

    coverage = (
        covered
        / reference
        * 100.0
    )

    return RegionalSTEXResult(
        covered_employment=
            round(
                covered,
                4,
            ),
        reference_employment=
            round(
                reference,
                4,
            ),
        coverage_rate=
            round(
                coverage,
                4,
            ),
        structural_exposure=
            round(
                exposure,
                4,
            ),
        occupation_count=
            len(
                [
                    row
                    for row in rows
                    if row.employment > 0
                ]
            ),
    )


def build_regional_stex_rows(
    *,
    employment_by_code:
        Mapping[str, float],
    exposure_by_code:
        Mapping[str, float],
) -> List[
    RegionalSTEXOccupation
]:
    """
    Join local employment and audited occupation STEX
    values by occupation code.

    Occupations without audited STEX values are excluded
    from the weighted score and therefore reduce coverage.
    """
    rows = []

    for code, employment in (
        employment_by_code.items()
    ):
        if code not in exposure_by_code:
            continue

        rows.append(
            RegionalSTEXOccupation(
                occupation_code=code,
                employment=float(
                    employment
                ),
                structural_exposure=float(
                    exposure_by_code[
                        code
                    ]
                ),
            )
        )

    return rows


def build_regional_stex_coverage_plan(
    *,
    total_employment: OEWSEmploymentEstimate,
    employment_rows: Iterable[OEWSEmploymentEstimate],
    profiles: Iterable[Mapping[str, Any]],
    occupation_titles: Optional[Mapping[str, str]] = None,
    recommendation_limit: int = 10,
) -> RegionalSTEXCoveragePlan:
    """Plan the next STEX audits from an explicit OEWS occupation universe.

    OEWS provides values for requested series but does not enumerate detailed
    occupations. The caller therefore supplies the authoritative SOC universe;
    rows without a profile remain unaudited and are never assigned zero STEX.
    """
    if recommendation_limit < 0:
        raise ValueError("recommendation_limit cannot be negative.")

    reference = float(total_employment.employment)
    if reference <= 0:
        raise ValueError("total_employment must be positive.")

    profile_by_soc: dict[str, Mapping[str, Any]] = {}
    for profile in profiles:
        code = profile.get("occupation_code")
        exposure = profile.get("structural_exposure")
        if not code or exposure is None:
            continue
        profile_by_soc[normalize_soc_code(str(code))] = profile

    title_by_soc = {
        normalize_soc_code(str(code)): str(title)
        for code, title in (occupation_titles or {}).items()
    }

    audited: list[RegionalSTEXOccupation] = []
    audited_details: list[dict[str, Any]] = []
    unaudited_details: list[dict[str, Any]] = []

    for row in employment_rows:
        if row.occupation_code == OEWS_ALL_OCCUPATIONS:
            continue
        if row.employment <= 0:
            continue

        base_code = normalize_soc_code(row.occupation_code)
        profile = profile_by_soc.get(base_code)
        title = title_by_soc.get(base_code)
        if title is None and profile is not None:
            title = str(profile.get("occupation_title") or "") or None

        detail = {
            "area_code": row.area_code,
            "source_year": row.year,
            "soc_code": row.occupation_code,
            "employment": round(row.employment, 4),
            "series_id": row.series_id,
            "source": row.source,
        }
        if row.catalog_source is not None:
            detail["catalog_source"] = row.catalog_source
        if title is not None:
            detail["occupation_title"] = title

        if profile is None:
            detail["potential_incremental_coverage"] = round(
                row.employment / reference * 100.0,
                4,
            )
            unaudited_details.append(detail)
            continue

        audited.append(
            RegionalSTEXOccupation(
                occupation_code=row.occupation_code,
                employment=row.employment,
                structural_exposure=float(
                    profile["structural_exposure"]
                ),
            )
        )
        detail["structural_exposure"] = float(
            profile["structural_exposure"]
        )
        if profile.get("source") is not None:
            detail["stex_source"] = profile["source"]
        audited_details.append(detail)

    result = aggregate_regional_stex(
        audited,
        reference_employment=reference,
    )

    audited_details.sort(key=lambda item: item["soc_code"])
    unaudited_details.sort(
        key=lambda item: (
            -float(item["employment"]),
            item["soc_code"],
        )
    )

    return RegionalSTEXCoveragePlan(
        area_code=total_employment.area_code,
        source_year=total_employment.year,
        total_employment=round(reference, 4),
        covered_employment=result.covered_employment,
        coverage_rate=result.coverage_rate,
        covered_stex=result.structural_exposure,
        contributing_audited_occupations=tuple(audited_details),
        recommended_unaudited_occupations=tuple(
            unaudited_details[:recommendation_limit]
        ),
        source=total_employment.source,
    )
