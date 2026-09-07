from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class OccupationMarketRecord:
    """
    National BLS occupational projection record.

    Employment and openings values from BLS projections are expressed
    in thousands in the source dataset.
    """

    soc_code: str
    title: str

    employment_base_thousands: Optional[float] = None
    employment_projected_thousands: Optional[float] = None
    employment_change_percent: Optional[float] = None
    annual_openings_thousands: Optional[float] = None

    median_annual_wage: Optional[float] = None

    education: str = ""
    related_experience: str = ""
    on_the_job_training: str = ""

    occupation_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def demand_outlook_score(record: OccupationMarketRecord) -> float:
    """
    Transparent v0.1 demand score.

    Combines projected employment growth with annual openings relative
    to base employment.

    This is deliberately simple and should later be calibrated against
    the national occupation distribution.
    """

    growth = record.employment_change_percent

    if growth is None:
        growth_score = 50.0
    else:
        # -20% maps to 0, +20% maps to 100.
        growth_score = ((growth + 20.0) / 40.0) * 100.0
        growth_score = max(0.0, min(100.0, growth_score))

    if (
        record.annual_openings_thousands is None
        or record.employment_base_thousands in (None, 0)
    ):
        openings_score = 50.0
    else:
        annual_opening_rate = (
            record.annual_openings_thousands
            / record.employment_base_thousands
        ) * 100.0

        # 0% annual opening rate -> 0
        # 15%+ annual opening rate -> 100
        openings_score = min(
            100.0,
            max(0.0, annual_opening_rate / 15.0 * 100.0),
        )

    return round(
        growth_score * 0.60 + openings_score * 0.40,
        2,
    )


def wage_retention_score(
    *,
    current_annual_wage: Optional[float],
    candidate_annual_wage: Optional[float],
) -> float:
    """
    Score 0-100 based on how much of a worker's current earnings
    a candidate occupation is expected to preserve.

    100 means candidate median wage meets or exceeds current earnings.
    """

    if (
        current_annual_wage is None
        or candidate_annual_wage is None
        or current_annual_wage <= 0
    ):
        return 50.0

    ratio = candidate_annual_wage / current_annual_wage

    return round(
        max(0.0, min(100.0, ratio * 100.0)),
        2,
    )


TRAINING_BURDEN = {
    "none": 10.0,
    "short-term on-the-job training": 20.0,
    "moderate-term on-the-job training": 40.0,
    "long-term on-the-job training": 65.0,
    "internship/residency": 75.0,
    "apprenticeship": 70.0,
}


EDUCATION_BURDEN = {
    "no formal educational credential": 5.0,
    "high school diploma or equivalent": 15.0,
    "some college, no degree": 25.0,
    "postsecondary nondegree award": 35.0,
    "associate's degree": 45.0,
    "bachelor's degree": 65.0,
    "master's degree": 78.0,
    "doctoral or professional degree": 95.0,
}


def retraining_burden_score(
    record: OccupationMarketRecord,
) -> float:
    """
    First-pass training burden using BLS education and OJT requirements.
    """

    education = EDUCATION_BURDEN.get(
        record.education.strip().lower(),
        50.0,
    )

    training = TRAINING_BURDEN.get(
        record.on_the_job_training.strip().lower(),
        35.0,
    )

    return round(
        education * 0.70 + training * 0.30,
        2,
    )
