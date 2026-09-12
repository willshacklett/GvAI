import json
from types import SimpleNamespace

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
import gvai.postlabor.sources.oews as oews_module
from gvai.postlabor.sources.oews_snapshot import (
    OEWS_MACHINE_SOURCE,
    OEWSSnapshotBuildError,
    build_snapshot_from_lines,
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


def test_fetch_regional_employment_returns_denominator_and_details():
    client = OEWSClient(
        bls_client=
            FakeBLSClient()
    )

    total, details = client.fetch_regional_employment(
        area_code="0034980",
        occupation_codes=[
            "15-1252.00",
            "37-2021.00",
        ],
        start_year=2025,
        end_year=2025,
    )

    assert total is not None
    assert total.employment == 1099300.0
    assert total.source == "BLS Public Data API v2"
    assert [item.occupation_code for item in details] == [
        "15-1252.00",
        "37-2021.00",
    ]
    assert all(
        item.source == "BLS Public Data API v2"
        for item in details
    )


def test_catalog_enumerates_only_nashville_detailed_employment_series(
    monkeypatch,
    tmp_path,
):
    files = {
        "oe.occupation": (
            "occupation_code\toccupation_name\t"
            "occupation_description\tdisplay_level\tselectable\t"
            "sort_sequence\n"
            "000000\tAll Occupations\t\t0\tT\t0\n"
            "110000\tManagement Occupations\t\t1\tT\t1\n"
            "151252\tSoftware Developers\tBuild software\t3\tT\t2\n"
            "372021\tPest Control Workers\tControl pests\t3\tT\t3\n"
        ),
        "oe.series": (
            "series_id\tseasonal\tareatype_code\tindustry_code\t"
            "occupation_code\tdatatype_code\tstate_code\tarea_code\t"
            "sector_code\tseries_title\tfootnote_codes\tbegin_year\t"
            "begin_period\tend_year\tend_period\n"
            "OEUM003498000000000000001\tU\tM\t000000\t000000\t01\t"
            "47\t0034980\t00--01\tAll Occupations\t\t2024\tA01\t"
            "2025\tA01\n"
            "OEUM003498000000015125201\tU\tM\t000000\t151252\t01\t"
            "47\t0034980\t00--01\tSoftware Developers\t\t2024\t"
            "A01\t2025\tA01\n"
            "OEUM003498000000037202101\tU\tM\t000000\t372021\t01\t"
            "47\t0034980\t00--01\tPest Control Workers\t\t2024\t"
            "A01\t2025\tA01\n"
            "OEUM003498000000011000001\tU\tM\t000000\t110000\t01\t"
            "47\t0034980\t00--01\tManagement Occupations\t\t2024\t"
            "A01\t2025\tA01\n"
            "OEUM003498000000015125202\tU\tM\t000000\t151252\t02\t"
            "47\t0034980\t00--01\tSoftware RSE\t\t2024\tA01\t"
            "2025\tA01\n"
            "OEUM003498000000015125201\tU\tM\t000000\t151252\t01\t"
            "47\t0010180\t00--01\tSoftware Developers\t\t2024\t"
            "A01\t2025\tA01\n"
        ),
    }

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, *, timeout, stream):
        return FakeResponse(files[url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(
        oews_module.requests,
        "get",
        fake_get,
    )

    client = OEWSClient(
        bls_client=FakeBLSClient(),
        catalog_base_url="https://catalog.test",
        catalog_cache_path=tmp_path / "oews.json",
    )

    assert client.refresh_catalog_cache() == 3
    series = client.fetch_catalog_detailed_occupations(
        area_code="0034980",
        source_year=2025,
    )

    assert [item.occupation_code for item in series] == [
        "15-1252.00",
        "37-2021.00",
    ]
    assert series[0].occupation_title == "Software Developers"
    assert series[0].series_id == (
        "OEUM003498000000015125201"
    )
    assert series[0].source_year == 2025
    assert series[0].source == "BLS OEWS time-series catalog"


def test_catalog_regional_fetch_preserves_titles_and_denominator(
    monkeypatch,
    tmp_path,
):
    occupation_file = (
        "occupation_code\toccupation_name\toccupation_description\t"
        "display_level\tselectable\tsort_sequence\n"
        "151252\tSoftware Developers\t\t3\tT\t2\n"
    )
    series_file = (
        "series_id\tseasonal\tareatype_code\tindustry_code\t"
        "occupation_code\tdatatype_code\tstate_code\tarea_code\t"
        "sector_code\tseries_title\tfootnote_codes\tbegin_year\t"
        "begin_period\tend_year\tend_period\n"
        "OEUM003498000000015125201\tU\tM\t000000\t151252\t01\t"
        "47\t0034980\t00--01\tSoftware Developers\t\t2024\tA01\t"
        "2025\tA01\n"
    )

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, *, timeout, stream):
        return FakeResponse(
            occupation_file
            if url.endswith("oe.occupation")
            else series_file
        )

    monkeypatch.setattr(
        oews_module.requests,
        "get",
        fake_get,
    )

    client = OEWSClient(
        bls_client=FakeBLSClient(),
        catalog_base_url="https://catalog.test",
        catalog_cache_path=tmp_path / "oews.json",
        employment_cache_path=tmp_path / "employment.json",
    )
    assert client.refresh_catalog_cache() == 1
    assert client.refresh_employment_cache(
        area_code="0034980",
        source_year=2025,
    ) == 1
    total, rows = client.fetch_catalog_regional_employment(
        area_code="0034980",
        source_year=2025,
    )

    assert total is not None
    assert total.employment == 1099300.0
    assert len(rows) == 1
    assert rows[0].occupation_title == "Software Developers"
    assert rows[0].occupation_code == "15-1252.00"
    assert rows[0].catalog_source == (
        "BLS OEWS time-series catalog"
    )


def test_catalog_cache_is_normalized_and_compact(tmp_path):
    cache = {
        "schema_version": 2,
        "source": "BLS OEWS time-series catalog",
        "datatype_code": "01",
        "industry_code": "000000",
        "occupations": {
            "151252": "Software Developers",
        },
        "areas": {
            "0034980": [
                {
                    "begin_year": 2024,
                    "end_year": 2025,
                    "occupations": ["15-1252.00"],
                }
            ]
        },
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(cache), encoding="utf-8")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert "records" not in payload
    assert "series_id" not in payload["areas"]["0034980"][0]
    assert "occupation_title" not in payload["areas"]["0034980"][0]
    assert payload["occupations"]["151252"] == "Software Developers"


def test_runtime_employment_lookup_uses_local_snapshot_without_network(
    monkeypatch,
    tmp_path,
):
    catalog_path = tmp_path / "catalog.json"
    employment_path = tmp_path / "employment.json"
    catalog_path.write_text(
        json.dumps({
            "schema_version": 2,
            "source": "BLS OEWS time-series catalog",
            "datatype_code": "01",
            "industry_code": "000000",
            "occupations": {"151252": "Software Developers"},
            "areas": {
                "0034980": [{
                    "begin_year": 2024,
                    "end_year": 2025,
                    "occupations": ["15-1252.00"],
                }]
            },
        }),
        encoding="utf-8",
    )
    employment_path.write_text(
        json.dumps({
            "schema_version": 1,
            "source": "BLS Public Data API v2",
            "observations": [{
                "area_code": "0034980",
                "occupation_code": "15-1252.00",
                "series_id": "OEUM003498000000015125201",
                "year": 2025,
                "employment": 7750.0,
                "occupation_title": "Software Developers",
                "source": "BLS Public Data API v2",
                "catalog_source": "BLS OEWS time-series catalog",
            }],
            "totals": [{
                "area_code": "0034980",
                "occupation_code": "00-0000.00",
                "series_id": "OEUM003498000000000000001",
                "year": 2025,
                "employment": 1099300.0,
                "source": "BLS Public Data API v2",
            }],
        }),
        encoding="utf-8",
    )
    def fail_network(*args, **kwargs):
        raise AssertionError("runtime attempted BLS network access")

    monkeypatch.setattr(oews_module.requests, "get", fail_network)
    client = OEWSClient(
        catalog_cache_path=catalog_path,
        employment_cache_path=employment_path,
    )
    series = client.fetch_catalog_detailed_occupations(
        area_code="0034980",
        source_year=2025,
    )
    total, rows = client.fetch_catalog_regional_employment(
        area_code="0034980",
        source_year=2025,
    )

    assert len(series) == 1
    assert total is not None
    assert total.employment == 1099300.0
    assert rows[0].employment == 7750.0
    assert rows[0].catalog_source == "BLS OEWS time-series catalog"


def test_employment_cache_isolates_area_year_and_missing_values(tmp_path):
    path = tmp_path / "employment.json"
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "source": "BLS Public Data API v2",
            "observations": [{
                "area_code": "0034980",
                "occupation_code": "15-1252.00",
                "series_id": "OEUM003498000000015125201",
                "year": 2025,
                "employment": 7750.0,
                "occupation_title": "Software Developers",
                "source": "BLS Public Data API v2",
            }],
            "totals": [{
                "area_code": "0034980",
                "occupation_code": "00-0000.00",
                "series_id": "OEUM003498000000000000001",
                "year": 2025,
                "employment": 1099300.0,
                "source": "BLS Public Data API v2",
            }],
        }),
        encoding="utf-8",
    )
    client = OEWSClient(employment_cache_path=path)
    total, rows = client.fetch_catalog_regional_employment(
        area_code="0034980",
        source_year=2025,
    )
    assert total is not None
    assert len(rows) == 1
    assert rows[0].employment == 7750.0
    with pytest.raises(RuntimeError, match="unavailable or stale"):
        client.fetch_catalog_regional_employment(
            area_code="0034980",
            source_year=2024,
        )
    with pytest.raises(RuntimeError, match="unavailable or stale"):
        client.fetch_catalog_regional_employment(
            area_code="0010180",
            source_year=2025,
        )
    assert all(row.employment != 0 for row in rows)


def test_employment_cache_path_precedence(monkeypatch, tmp_path):
    explicit = tmp_path / "explicit.json"
    env_path = tmp_path / "env.json"
    packaged = tmp_path / "packaged.json"
    monkeypatch.setenv("GVAI_OEWS_EMPLOYMENT_CACHE", str(env_path))
    monkeypatch.setattr(
        oews_module,
        "OEWS_PACKAGED_EMPLOYMENT_CACHE_PATH",
        packaged,
    )

    assert OEWSClient(employment_cache_path=explicit).employment_cache_path == explicit
    assert OEWSClient().employment_cache_path == env_path

    monkeypatch.delenv("GVAI_OEWS_EMPLOYMENT_CACHE")
    packaged.write_text("{}", encoding="utf-8")
    assert OEWSClient().employment_cache_path == packaged


def test_machine_readable_builder_filters_series_and_preserves_provenance():
    detail = SimpleNamespace(
        area_code="0034980",
        occupation_code="15-1252.00",
        occupation_title="Software Developers",
        series_id="OEUM003498000000015125201",
        source_year=2025,
        source="BLS OEWS time-series catalog",
        display_level=3,
    )
    aggregate = SimpleNamespace(
        area_code="0034980",
        occupation_code="150000.00",
        occupation_title="Computer and Mathematical Occupations",
        series_id="OEUM003498000000015000001",
        source_year=2025,
        source="BLS OEWS time-series catalog",
        display_level=1,
    )
    lines = [
        "series_id\tyear\tperiod\tvalue\tfootnote_codes\n",
        "OEUM003498000000015125201\t2024\tA01\t7000\t\n",
        "OEUM003498000000015125201\t2025\tM12\t7000\t\n",
        "OEUM001018000000015125201\t2025\tA01\t9999\t\n",
        "OEUM003498000000015000001\t2025\tA01\t50000\t\n",
        "OEUM003498000000015125201\t2025\tA01\t7750\t\n",
        "OEUM003498000000000000001\t2025\tA01\t1099300\t\n",
    ]

    snapshot = build_snapshot_from_lines(
        lines,
        area_code="0034980",
        source_year=2025,
        catalog_rows=[detail, aggregate],
        generated_at="2026-09-12T00:00:00+00:00",
    )

    assert len(snapshot["observations"]) == 1
    assert snapshot["observations"][0]["employment"] == 7750.0
    assert snapshot["observations"][0]["occupation_title"] == (
        "Software Developers"
    )
    assert snapshot["totals"][0]["employment"] == 1099300.0
    assert snapshot["source"] == OEWS_MACHINE_SOURCE
    assert snapshot["source_years"] == [2025]
    assert snapshot["generated_at"] == "2026-09-12T00:00:00+00:00"
    assert snapshot["suppressed_or_missing_count"] == 0


def test_machine_readable_builder_omits_suppressed_and_requires_denominator():
    detail = SimpleNamespace(
        area_code="0034980",
        occupation_code="15-1252.00",
        occupation_title="Software Developers",
        series_id="OEUM003498000000015125201",
        source_year=2025,
        source="BLS OEWS time-series catalog",
    )
    lines = [
        "series_id\tyear\tperiod\tvalue\tfootnote_codes\n",
        "OEUM003498000000015125201\t2025\tA01\t#\tS\n",
    ]
    with pytest.raises(OEWSSnapshotBuildError, match="denominator"):
        build_snapshot_from_lines(
            lines,
            area_code="0034980",
            source_year=2025,
            catalog_rows=[detail],
        )


def test_machine_readable_builder_rejects_duplicate_observations():
    detail = SimpleNamespace(
        area_code="0034980",
        occupation_code="15-1252.00",
        occupation_title="Software Developers",
        series_id="OEUM003498000000015125201",
        source_year=2025,
        source="BLS OEWS time-series catalog",
    )
    lines = [
        "series_id\tyear\tperiod\tvalue\tfootnote_codes\n",
        "OEUM003498000000015125201\t2025\tA01\t7750\t\n",
        "OEUM003498000000015125201\t2025\tA01\t7750\t\n",
        "OEUM003498000000000000001\t2025\tA01\t1099300\t\n",
    ]
    with pytest.raises(OEWSSnapshotBuildError, match="Duplicate"):
        build_snapshot_from_lines(
            lines,
            area_code="0034980",
            source_year=2025,
            catalog_rows=[detail],
        )


def test_generated_snapshot_round_trips_through_oews_client(tmp_path):
    detail = SimpleNamespace(
        area_code="0034980",
        occupation_code="15-1252.00",
        occupation_title="Software Developers",
        series_id="OEUM003498000000015125201",
        source_year=2025,
        source="BLS OEWS time-series catalog",
        display_level=3,
    )
    snapshot = build_snapshot_from_lines(
        [
            "series_id\tyear\tperiod\tvalue\tfootnote_codes\n",
            "OEUM003498000000015125201\t2025\tA01\t7750\t\n",
            "OEUM003498000000000000001\t2025\tA01\t1099300\t\n",
        ],
        area_code="0034980",
        source_year=2025,
        catalog_rows=[detail],
    )
    path = tmp_path / "employment.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    total, rows = OEWSClient(
        employment_cache_path=path,
    ).fetch_catalog_regional_employment(
        area_code="0034980",
        source_year=2025,
    )

    assert total is not None
    assert total.employment == 1099300.0
    assert rows[0].employment == 7750.0
    assert rows[0].source == OEWS_MACHINE_SOURCE
    assert rows[0].catalog_source == "BLS OEWS time-series catalog"


def test_catalog_regional_fetch_rejects_empty_detailed_universe(
    monkeypatch,
    tmp_path,
):
    occupation_file = (
        "occupation_code\toccupation_name\toccupation_description\t"
        "display_level\tselectable\tsort_sequence\n"
        "000000\tAll Occupations\t\t0\tT\t0\n"
    )
    series_file = (
        "series_id\tseasonal\tareatype_code\tindustry_code\t"
        "occupation_code\tdatatype_code\tstate_code\tarea_code\t"
        "sector_code\tseries_title\tfootnote_codes\tbegin_year\t"
        "begin_period\tend_year\tend_period\n"
    )

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, *, timeout, stream):
        return FakeResponse(
            occupation_file
            if url.endswith("oe.occupation")
            else series_file
        )

    monkeypatch.setattr(
        oews_module.requests,
        "get",
        fake_get,
    )

    client = OEWSClient(
        bls_client=FakeBLSClient(),
        catalog_base_url="https://catalog.test",
        catalog_cache_path=tmp_path / "oews.json",
        employment_cache_path=tmp_path / "missing-employment.json",
    )

    assert client.refresh_catalog_cache() == 0
    with pytest.raises(RuntimeError, match="employment cache is missing"):
        client.fetch_catalog_regional_employment(
            area_code="0034980",
            source_year=2025,
        )


def test_catalog_lookup_reuses_cache_without_redownloading(
    monkeypatch,
    tmp_path,
):
    files = {
        "oe.occupation": (
            "occupation_code\toccupation_name\t"
            "occupation_description\tdisplay_level\tselectable\t"
            "sort_sequence\n"
            "151252\tSoftware Developers\t\t3\tT\t2\n"
        ),
        "oe.series": (
            "series_id\tseasonal\tareatype_code\tindustry_code\t"
            "occupation_code\tdatatype_code\tstate_code\tarea_code\t"
            "sector_code\tseries_title\tfootnote_codes\tbegin_year\t"
            "begin_period\tend_year\tend_period\n"
            "OEUM003498000000015125201\tU\tM\t000000\t151252\t01\t"
            "47\t0034980\t00--01\tSoftware Developers\t\t2024\t"
            "A01\t2025\tA01\n"
        ),
    }
    calls = []

    class FakeResponse:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            return None

    def fake_get(url, *, timeout, stream):
        calls.append(url)
        return FakeResponse(files[url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(oews_module.requests, "get", fake_get)
    client = OEWSClient(
        catalog_base_url="https://catalog.test",
        catalog_cache_path=tmp_path / "oews.json",
    )
    client.refresh_catalog_cache()
    client.fetch_catalog_detailed_occupations(area_code="0034980")
    client.fetch_catalog_detailed_occupations(area_code="0034980")

    assert calls == [
        "https://catalog.test/oe.occupation",
        "https://catalog.test/oe.series",
    ]


def test_catalog_lookup_missing_or_stale_cache_fails_explicitly(tmp_path):
    client = OEWSClient(catalog_cache_path=tmp_path / "missing.json")
    with pytest.raises(RuntimeError, match="cache is missing"):
        client.fetch_catalog_detailed_occupations(area_code="0034980")

    (tmp_path / "stale.json").write_text(
        '{"schema_version": 0, "records": []}\n',
        encoding="utf-8",
    )
    stale_client = OEWSClient(catalog_cache_path=tmp_path / "stale.json")
    with pytest.raises(RuntimeError, match="stale or incompatible"):
        stale_client.fetch_catalog_detailed_occupations(
            area_code="0034980"
        )
