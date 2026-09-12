import pytest

from gvai.postlabor.stex.regional import (
    RegionalSTEXOccupation,
    aggregate_regional_stex,
    build_regional_stex_rows,
)


def test_regional_stex_weighting():
    result = aggregate_regional_stex(
        [
            RegionalSTEXOccupation(
                occupation_code=
                    "15-1252.00",
                employment=
                    7750.0,
                structural_exposure=
                    75.9444,
            ),
            RegionalSTEXOccupation(
                occupation_code=
                    "37-2021.00",
                employment=
                    1050.0,
                structural_exposure=
                    35.6614,
            ),
        ],
        reference_employment=
            100000.0,
    )

    expected = (
        (
            7750.0
            * 75.9444
        )
        +
        (
            1050.0
            * 35.6614
        )
    ) / 8800.0

    assert (
        result.covered_employment
        == 8800.0
    )

    assert (
        result.reference_employment
        == 100000.0
    )

    assert (
        result.coverage_rate
        == 8.8
    )

    assert (
        result.structural_exposure
        == round(
            expected,
            4,
        )
    )

    assert (
        result.occupation_count
        == 2
    )


def test_zero_coverage():
    result = aggregate_regional_stex(
        [],
        reference_employment=
            1000.0,
    )

    assert (
        result.covered_employment
        == 0.0
    )

    assert (
        result.coverage_rate
        == 0.0
    )

    assert (
        result.structural_exposure
        == 0.0
    )

    assert (
        result.occupation_count
        == 0
    )


def test_rejects_bad_reference():
    with pytest.raises(
        ValueError
    ):
        aggregate_regional_stex(
            [],
            reference_employment=
                0,
        )


def test_rejects_covered_above_reference():
    with pytest.raises(
        ValueError
    ):
        aggregate_regional_stex(
            [
                RegionalSTEXOccupation(
                    occupation_code=
                        "15-1252.00",
                    employment=
                        1200,
                    structural_exposure=
                        50,
                )
            ],
            reference_employment=
                1000,
        )


def test_rejects_bad_exposure():
    with pytest.raises(
        ValueError
    ):
        aggregate_regional_stex(
            [
                RegionalSTEXOccupation(
                    occupation_code=
                        "15-1252.00",
                    employment=
                        100,
                    structural_exposure=
                        120,
                )
            ],
            reference_employment=
                1000,
        )


def test_join_only_audited_occupations():
    rows = build_regional_stex_rows(
        employment_by_code={
            "15-1252.00": 7750,
            "37-2021.00": 1050,
            "11-1011.00": 5000,
        },
        exposure_by_code={
            "15-1252.00": 75.9444,
            "37-2021.00": 35.6614,
        },
    )

    assert len(rows) == 2

    codes = {
        row.occupation_code
        for row in rows
    }

    assert codes == {
        "15-1252.00",
        "37-2021.00",
    }
