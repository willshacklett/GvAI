import json
from types import SimpleNamespace

import pytest

from gvai.postlabor.sources.oews import (
    OEWSClient,
    OEWSWageEstimate,
    build_oews_series_id,
)
from gvai.postlabor.sources.oews_snapshot import OEWSSnapshotBuildError
from gvai.postlabor.sources.oews_wage_snapshot import (
    build_multi_area_wage_snapshot_from_lines,
    validate_preserved_wage_area,
)


def _detail(area_code, occupation_code, occupation_title, source_year=2025):
    return SimpleNamespace(
        area_code=area_code,
        occupation_code=occupation_code,
        occupation_title=occupation_title,
        source_year=source_year,
        source="BLS OEWS time-series catalog",
        display_level=3,
    )


def test_wage_builder_reads_hourly_and_annual_datatypes():
    """Nashville OEWS area 0034980, Pest Control Workers 37-2021.00, 2025:
    hourly median wage 21.32, annual median wage 44350."""
    detail = _detail("0034980", "37-2021.00", "Pest Control Workers")
    hourly_series = build_oews_series_id(
        area_code="0034980",
        occupation_code="37-2021.00",
        datatype_code="08",
    )
    annual_series = build_oews_series_id(
        area_code="0034980",
        occupation_code="37-2021.00",
        datatype_code="13",
    )
    lines = [
        "series_id\tyear\tperiod\tvalue\tfootnote_codes\n",
        f"{hourly_series}\t2025\tA01\t21.32\t\n",
        f"{annual_series}\t2025\tA01\t44350\t\n",
    ]

    snapshot = build_multi_area_wage_snapshot_from_lines(
        lines,
        area_codes=["0034980"],
        source_year=2025,
        catalog_rows=[detail],
        generated_at="2026-09-17T00:00:00+00:00",
    )

    assert len(snapshot["observations"]) == 1
    observation = snapshot["observations"][0]
    assert observation["median_hourly_wage"] == 21.32
    assert observation["median_annual_wage"] == 44350.0
    assert observation["occupation_code"] == "37-2021.00"
    assert observation["occupation_title"] == "Pest Control Workers"
    assert observation["year"] == 2025
    assert snapshot["suppressed_or_missing_count"] == 0


def test_wage_builder_leaves_suppressed_values_null_not_zero():
    detail = _detail("0034980", "37-2021.00", "Pest Control Workers")
    hourly_series = build_oews_series_id(
        area_code="0034980",
        occupation_code="37-2021.00",
        datatype_code="08",
    )
    annual_series = build_oews_series_id(
        area_code="0034980",
        occupation_code="37-2021.00",
        datatype_code="13",
    )
    lines = [
        "series_id\tyear\tperiod\tvalue\tfootnote_codes\n",
        f"{hourly_series}\t2025\tA01\t#\tS\n",
        f"{annual_series}\t2025\tA01\t#\tS\n",
    ]

    snapshot = build_multi_area_wage_snapshot_from_lines(
        lines,
        area_codes=["0034980"],
        source_year=2025,
        catalog_rows=[detail],
    )

    observation = snapshot["observations"][0]
    assert observation["median_hourly_wage"] is None
    assert observation["median_annual_wage"] is None
    assert snapshot["suppressed_or_missing_count"] == 2

    serialized = json.dumps(snapshot)
    assert '"median_hourly_wage": 0' not in serialized
    assert '"median_annual_wage": 0' not in serialized


def test_wage_builder_rejects_duplicate_observations():
    detail = _detail("0034980", "37-2021.00", "Pest Control Workers")
    hourly_series = build_oews_series_id(
        area_code="0034980",
        occupation_code="37-2021.00",
        datatype_code="08",
    )
    lines = [
        "series_id\tyear\tperiod\tvalue\tfootnote_codes\n",
        f"{hourly_series}\t2025\tA01\t21.32\t\n",
        f"{hourly_series}\t2025\tA01\t21.32\t\n",
    ]

    with pytest.raises(OEWSSnapshotBuildError, match="Duplicate"):
        build_multi_area_wage_snapshot_from_lines(
            lines,
            area_codes=["0034980"],
            source_year=2025,
            catalog_rows=[detail],
        )


def test_validate_preserved_wage_area_rejects_changed_values():
    baseline = {
        "observations": [
            {"area_code": "0034980", "occupation_code": "37-2021.00"},
        ],
    }
    validate_preserved_wage_area(
        existing_snapshot=baseline,
        replacement_snapshot=baseline,
        area_code="0034980",
    )
    with pytest.raises(OEWSSnapshotBuildError, match="wage observations"):
        validate_preserved_wage_area(
            existing_snapshot=baseline,
            replacement_snapshot={"observations": []},
            area_code="0034980",
        )


def test_runtime_wage_lookup_uses_local_snapshot_without_network(
    monkeypatch, tmp_path
):
    wage_path = tmp_path / "wage.json"
    wage_path.write_text(
        json.dumps({
            "schema_version": 1,
            "source": "BLS OEWS time-series machine-readable data",
            "observations": [{
                "area_code": "0034980",
                "occupation_code": "37-2021.00",
                "occupation_title": "Pest Control Workers",
                "year": 2025,
                "median_hourly_wage": 21.32,
                "median_annual_wage": 44350.0,
                "source": "BLS OEWS time-series machine-readable data",
                "catalog_source": "BLS OEWS time-series catalog",
            }],
        }),
        encoding="utf-8",
    )

    import gvai.postlabor.sources.oews as oews_module

    def fail_network(*args, **kwargs):
        raise AssertionError("runtime attempted BLS network access")

    monkeypatch.setattr(oews_module.requests, "get", fail_network)

    client = OEWSClient(wage_cache_path=wage_path)
    rows = client.fetch_catalog_regional_wages(
        area_code="0034980",
        source_year=2025,
    )

    assert len(rows) == 1
    assert isinstance(rows[0], OEWSWageEstimate)
    assert rows[0].median_hourly_wage == 21.32
    assert rows[0].median_annual_wage == 44350.0


def test_wage_cache_missing_raises_runtime_error(tmp_path):
    client = OEWSClient(wage_cache_path=tmp_path / "missing.json")
    with pytest.raises(RuntimeError, match="wage cache is missing"):
        client.fetch_catalog_regional_wages(
            area_code="0034980",
            source_year=2025,
        )
