from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional

import requests

from gvai.postlabor.sources.oews import (
    OEWS_ALL_OCCUPATIONS,
    OEWS_CATALOG_SOURCE,
    OEWS_SOURCE,
    OEWSClient,
    build_oews_series_id,
    normalize_area_code,
)


OEWS_MACHINE_SOURCE = "BLS OEWS time-series machine-readable data"
OEWS_MACHINE_DATA_URL = (
    "https://download.bls.gov/pub/time.series/oe/oe.data.0.Current"
)
OEWS_MACHINE_MIRROR_URL = (
    "https://downloadt.bls.gov/pub/time.series/oe/oe.data.0.Current"
)
OEWS_SNAPSHOT_SCHEMA_VERSION = 2


class OEWSSnapshotBuildError(ValueError):
    pass


def _iter_tab_records(lines: Iterable[str]):
    iterator = iter(lines)
    try:
        header_line = next(iterator)
    except StopIteration:
        return
    if isinstance(header_line, bytes):
        header_line = header_line.decode("utf-8")
    headers = [item.strip() for item in header_line.split("\t")]
    required = {"series_id", "year", "period", "value"}
    if not required.issubset(headers):
        raise OEWSSnapshotBuildError(
            "OEWS machine-readable data is missing required columns."
        )
    for raw_line in iterator:
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        values = line.rstrip("\r\n").split("\t")
        if len(values) != len(headers):
            continue
        yield {
            header: value.strip()
            for header, value in zip(headers, values)
        }


def build_snapshot_from_lines(
    lines: Iterable[str],
    *,
    area_code: str,
    source_year: int,
    catalog_rows: Iterable[object],
    source_url: str = OEWS_MACHINE_DATA_URL,
    generated_at: Optional[str] = None,
) -> dict:
    """Build one local snapshot while consuming only the supplied data stream."""
    area = normalize_area_code(area_code)
    detail_by_series = {
        item.series_id: item
        for item in catalog_rows
        if item.area_code == area
        and item.source_year == source_year
        and getattr(item, "display_level", 3) == 3
    }
    if not detail_by_series:
        raise OEWSSnapshotBuildError(
            "The catalog has no detailed occupations for the requested area/year."
        )
    total_series_id = build_oews_series_id(
        area_code=area,
        occupation_code=OEWS_ALL_OCCUPATIONS,
    )
    wanted_series = set(detail_by_series) | {total_series_id}
    observations = []
    totals = []
    seen = set()
    suppressed_or_missing_count = 0

    for fields in _iter_tab_records(lines):
        series_id = fields["series_id"]
        if series_id not in wanted_series:
            continue
        if fields["period"] != "A01":
            continue
        try:
            row_year = int(fields["year"])
        except (TypeError, ValueError):
            continue
        if row_year != source_year:
            continue
        key = (series_id, row_year, fields["period"])
        if key in seen:
            raise OEWSSnapshotBuildError(
                f"Duplicate OEWS observation for series {series_id}."
            )
        seen.add(key)
        try:
            employment = float(fields["value"])
        except (TypeError, ValueError):
            suppressed_or_missing_count += 1
            continue
        if employment < 0:
            suppressed_or_missing_count += 1
            continue
        if series_id == total_series_id:
            totals.append({
                "area_code": area,
                "occupation_code": OEWS_ALL_OCCUPATIONS,
                "occupation_title": "All Occupations",
                "series_id": series_id,
                "year": source_year,
                "employment": employment,
                "source": OEWS_MACHINE_SOURCE,
                "catalog_source": OEWS_CATALOG_SOURCE,
                "source_url": source_url,
            })
            continue
        item = detail_by_series[series_id]
        observations.append({
            "area_code": area,
            "occupation_code": item.occupation_code,
            "occupation_title": item.occupation_title,
            "series_id": series_id,
            "year": source_year,
            "employment": employment,
            "source": OEWS_MACHINE_SOURCE,
            "catalog_source": item.source,
            "source_url": source_url,
        })

    if len(totals) != 1:
        raise OEWSSnapshotBuildError(
            "Exactly one numeric All Occupations denominator is required."
        )
    observations.sort(key=lambda item: item["occupation_code"])
    return {
        "schema_version": OEWS_SNAPSHOT_SCHEMA_VERSION,
        "source": OEWS_MACHINE_SOURCE,
        "source_url": source_url,
        "catalog_source": OEWS_CATALOG_SOURCE,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "source_years": [source_year],
        "areas": [area],
        "suppressed_or_missing_count": suppressed_or_missing_count,
        "observations": observations,
        "totals": totals,
    }


def build_employment_snapshot(
    *,
    area_code: str,
    source_year: int,
    output_path: Path | str,
    catalog_client: Optional[OEWSClient] = None,
    data_url: str = OEWS_MACHINE_DATA_URL,
    timeout: int = 120,
) -> dict:
    """Ingest official OEWS data and write a deployable regional snapshot."""
    client = catalog_client or OEWSClient()
    try:
        catalog_rows = client.fetch_catalog_detailed_occupations(
            area_code=area_code,
            source_year=source_year,
        )
    except RuntimeError:
        client.refresh_catalog_cache()
        catalog_rows = client.fetch_catalog_detailed_occupations(
            area_code=area_code,
            source_year=source_year,
        )

    response = requests.get(data_url, timeout=timeout, stream=True)
    if getattr(response, "status_code", 200) == 403 and data_url == OEWS_MACHINE_DATA_URL:
        response = requests.get(
            OEWS_MACHINE_MIRROR_URL,
            timeout=timeout,
            stream=True,
        )
    response.raise_for_status()
    snapshot = build_snapshot_from_lines(
        response.iter_lines(decode_unicode=True),
        area_code=area_code,
        source_year=source_year,
        catalog_rows=catalog_rows,
        source_url=data_url,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build an offline OEWS snapshot.")
    parser.add_argument("--area", required=True)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    snapshot = build_employment_snapshot(
        area_code=args.area,
        source_year=args.year,
        output_path=args.output,
    )
    print(f"area: {args.area}")
    print(f"year: {args.year}")
    print(f"detailed rows: {len(snapshot['observations'])}")
    print(f"total employment: {snapshot['totals'][0]['employment']}")
    print(f"output path: {args.output}")
    print(f"output size: {args.output.stat().st_size} bytes")
    print(f"source: {snapshot['source']}")
    print(f"source URL: {snapshot['source_url']}")
    print(f"suppressed/missing: {snapshot['suppressed_or_missing_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
