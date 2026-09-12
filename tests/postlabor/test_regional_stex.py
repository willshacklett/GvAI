import pytest

from gvai.postlabor.sources.oews import (
    OEWSEmploymentEstimate,
)
from gvai.postlabor.stex.regional import (
    RegionalSTEXOccupation,
    aggregate_regional_stex,
    build_regional_stex_rows,
    build_regional_stex_coverage_plan,
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


def test_coverage_plan_preserves_coverage_and_ranks_unaudited():
    total = OEWSEmploymentEstimate(
        area_code="0034980",
        occupation_code="00-0000.00",
        series_id="OEUM003498000000000000001",
        year=2025,
        employment=1099300.0,
    )

    rows = [
        OEWSEmploymentEstimate(
            area_code="0034980",
            occupation_code="15-1252.00",
            series_id="OEUM003498000000015125201",
            year=2025,
            employment=7750.0,
        ),
        OEWSEmploymentEstimate(
            area_code="0034980",
            occupation_code="37-2021.00",
            series_id="OEUM003498000000037202101",
            year=2025,
            employment=1050.0,
        ),
        OEWSEmploymentEstimate(
            area_code="0034980",
            occupation_code="35-2012.00",
            series_id="OEUM003498000000035201201",
            year=2025,
            employment=12000.0,
        ),
        OEWSEmploymentEstimate(
            area_code="0034980",
            occupation_code="31-1120.00",
            series_id="OEUM003498000000031112001",
            year=2025,
            employment=9000.0,
        ),
    ]

    plan = build_regional_stex_coverage_plan(
        total_employment=total,
        employment_rows=rows,
        profiles=[
            {
                "occupation_code": "15-1252.00",
                "occupation_title": "Software Developers",
                "structural_exposure": 75.9444,
                "source": {"name": "STEX v0.1"},
            },
            {
                "occupation_code": "37-2021.00",
                "occupation_title": "Pest Control Workers",
                "structural_exposure": 35.6614,
                "source": {"name": "STEX v0.1"},
            },
        ],
        occupation_titles={
            "35-2012.00": "Cooks, Institution and Cafeteria",
            "31-1120.00": "Home Health and Personal Care Aides",
        },
        recommendation_limit=2,
    )

    assert plan.area_code == "0034980"
    assert plan.source_year == 2025
    assert plan.total_employment == 1099300.0
    assert plan.covered_employment == 8800.0
    assert plan.coverage_rate == 0.8005
    assert plan.covered_stex == 71.1379

    assert [
        item["soc_code"]
        for item in plan.contributing_audited_occupations
    ] == ["15-1252.00", "37-2021.00"]

    assert [
        item["soc_code"]
        for item in plan.recommended_unaudited_occupations
    ] == ["35-2012.00", "31-1120.00"]
    assert (
        plan.recommended_unaudited_occupations[0][
            "potential_incremental_coverage"
        ]
        == 1.0916
    )
    assert all(
        "structural_exposure" not in item
        for item in plan.recommended_unaudited_occupations
    )

    payload = plan.to_dict()
    assert payload["coverage_percentage"] == 0.8005
    assert payload["source"] == "BLS Public Data API v2"
