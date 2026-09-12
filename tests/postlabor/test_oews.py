import pytest

from gvai.postlabor.sources.bls import (
    BLSDatapoint,
    BLSSeries,
)
from gvai.postlabor.sources.oews import (
    OEWSClient,
    build_oews_series_id,
    normalize_area_code,
    normalize_soc_code,
)


def test_normalize_soc_code():
    assert (
        normalize_soc_code(
            "15-1252.00"
        )
        == "151252"
    )

    assert (
        normalize_soc_code(
            "37-2021"
        )
        == "372021"
    )


def test_normalize_soc_code_rejects_bad_value():
    with pytest.raises(
        ValueError
    ):
        normalize_soc_code(
            "software"
        )


def test_normalize_area_code():
    assert (
        normalize_area_code(
            "0034980"
        )
        == "0034980"
    )


def test_normalize_area_code_rejects_bad_value():
    with pytest.raises(
        ValueError
    ):
        normalize_area_code(
            "34980"
        )


def test_build_software_developer_series():
    assert (
        build_oews_series_id(
            area_code=
                "0034980",
            occupation_code=
                "15-1252.00",
        )
        ==
        "OEUM003498000000015125201"
    )


def test_build_pest_control_series():
    assert (
        build_oews_series_id(
            area_code=
                "0034980",
            occupation_code=
                "37-2021.00",
        )
        ==
        "OEUM003498000000037202101"
    )


class FakeBLSClient:
    def fetch_series(
        self,
        series_ids,
        *,
        start_year=None,
        end_year=None,
    ):
        ids = list(series_ids)

        values = {
            "OEUM003498000000000000001":
                1099300.0,
            "OEUM003498000000015125201":
                7750.0,
            "OEUM003498000000037202101":
                1050.0,
        }

        return [
            BLSSeries(
                series_id=series_id,
                data=[
                    BLSDatapoint(
                        series_id=
                            series_id,
                        year=2025,
                        period="A01",
                        period_name=
                            "Annual",
                        value=
                            values[
                                series_id
                            ],
                    )
                ],
            )
            for series_id
            in ids
        ]


def test_fetch_employment():
    client = OEWSClient(
        bls_client=
            FakeBLSClient()
    )

    result = (
        client.fetch_employment(
            area_code=
                "0034980",
            occupation_codes=[
                "15-1252.00",
                "37-2021.00",
            ],
            start_year=2025,
            end_year=2025,
        )
    )

    assert len(result) == 2

    by_code = {
        item.occupation_code:
            item
        for item in result
    }

    assert (
        by_code[
            "15-1252.00"
        ].employment
        == 7750.0
    )

    assert (
        by_code[
            "37-2021.00"
        ].employment
        == 1050.0
    )

    assert (
        by_code[
            "15-1252.00"
        ].year
        == 2025
    )


def test_fetch_total_employment():
    client = OEWSClient(
        bls_client=
            FakeBLSClient()
    )

    result = (
        client.fetch_total_employment(
            area_code=
                "0034980",
            start_year=2025,
            end_year=2025,
        )
    )

    assert result is not None

    assert (
        result.occupation_code
        == "00-0000.00"
    )

    assert (
        result.series_id
        ==
        "OEUM003498000000000000001"
    )

    assert (
        result.employment
        == 1099300.0
    )

    assert result.year == 2025
