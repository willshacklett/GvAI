from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from gvai.postlabor.sources.bls import (
    BLSClient,
)


OEWS_EMPLOYMENT_DATATYPE = "01"
OEWS_TOTAL_INDUSTRY = "000000"


def normalize_soc_code(
    occupation_code: str,
) -> str:
    """
    Convert an O*NET/SOC-style occupation code to the
    6-digit occupation field used by OEWS series IDs.

    Examples:
        15-1252.00 -> 151252
        15-1252    -> 151252
    """
    value = (
        str(occupation_code)
        .strip()
        .split(".", 1)[0]
        .replace("-", "")
    )

    if (
        len(value) != 6
        or not value.isdigit()
    ):
        raise ValueError(
            "Occupation code must look like "
            "15-1252 or 15-1252.00."
        )

    return value


def normalize_area_code(
    area_code: str,
) -> str:
    """
    OEWS metropolitan area codes use a 7-digit field.

    Example:
        Nashville-Davidson--Murfreesboro--Franklin
        0034980
    """
    value = str(area_code).strip()

    if (
        len(value) != 7
        or not value.isdigit()
    ):
        raise ValueError(
            "OEWS area code must contain exactly "
            "7 digits, such as 0034980."
        )

    return value


def build_oews_series_id(
    *,
    area_code: str,
    occupation_code: str,
    datatype_code: str = (
        OEWS_EMPLOYMENT_DATATYPE
    ),
    industry_code: str = (
        OEWS_TOTAL_INDUSTRY
    ),
) -> str:
    """
    Build an OEWS metropolitan-area series ID.

    Proven production example:

        OEUM003498000000015125201

    Structure:
        OE
        U
        M
        <7-digit area>
        <6-digit industry>
        <6-digit occupation>
        <2-digit datatype>
    """
    area = normalize_area_code(
        area_code
    )

    occupation = normalize_soc_code(
        occupation_code
    )

    industry = str(
        industry_code
    ).strip()

    datatype = str(
        datatype_code
    ).strip()

    if (
        len(industry) != 6
        or not industry.isdigit()
    ):
        raise ValueError(
            "OEWS industry code must contain "
            "exactly 6 digits."
        )

    if (
        len(datatype) != 2
        or not datatype.isdigit()
    ):
        raise ValueError(
            "OEWS datatype code must contain "
            "exactly 2 digits."
        )

    return (
        "OE"
        "U"
        "M"
        + area
        + industry
        + occupation
        + datatype
    )


@dataclass(frozen=True)
class OEWSEmploymentEstimate:
    area_code: str
    occupation_code: str
    series_id: str
    year: int
    employment: float

    def to_dict(self):
        return {
            "area_code":
                self.area_code,
            "occupation_code":
                self.occupation_code,
            "series_id":
                self.series_id,
            "year":
                self.year,
            "employment":
                self.employment,
        }


class OEWSClient:
    """
    Thin occupation-employment layer over the
    existing BLS Public Data API client.
    """

    def __init__(
        self,
        bls_client: Optional[
            BLSClient
        ] = None,
    ) -> None:
        self.bls_client = (
            bls_client
            or BLSClient()
        )

    def fetch_employment(
        self,
        *,
        area_code: str,
        occupation_codes:
            Iterable[str],
        start_year:
            Optional[int] = None,
        end_year:
            Optional[int] = None,
    ) -> List[
        OEWSEmploymentEstimate
    ]:
        codes = [
            str(code).strip()
            for code
            in occupation_codes
            if str(code).strip()
        ]

        if not codes:
            return []

        series_map = {}

        for code in codes:
            series_id = (
                build_oews_series_id(
                    area_code=area_code,
                    occupation_code=code,
                )
            )

            series_map[
                series_id
            ] = code

        series = (
            self.bls_client
            .fetch_series(
                series_map.keys(),
                start_year=start_year,
                end_year=end_year,
            )
        )

        results = []

        for item in series:
            point = item.latest()

            if point is None:
                continue

            original_code = (
                series_map.get(
                    item.series_id
                )
            )

            if original_code is None:
                continue

            results.append(
                OEWSEmploymentEstimate(
                    area_code=
                        normalize_area_code(
                            area_code
                        ),
                    occupation_code=
                        original_code,
                    series_id=
                        item.series_id,
                    year=
                        point.year,
                    employment=
                        point.value,
                )
            )

        return results
