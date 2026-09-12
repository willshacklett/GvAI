from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping


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
