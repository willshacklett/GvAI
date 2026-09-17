"""Builder for packaged official OEWS median wage snapshots.

Uses the same BLS OEWS time-series machine-readable data file as the
existing employment snapshot builder, but reads the median wage
datatypes instead of the employment datatype:

    08 = hourly median wage
    13 = annual median wage

This module is purely an ingestion-time tool. Runtime lookups never
call BLS directly; they read the packaged local snapshot produced here.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional

import requests

from gvai.postlabor.sources.oews import (
    OEWSClient,
    OEWS_ANNUAL_MEDIAN_WAGE_DATATYPE,
    OEWS_HOURLY_MEDIAN_WAGE_DATATYPE,
    build_oews_series_id,
    normalize_area_code,
)
from gvai.postlabor.sources.oews_snapshot import (
    OEWS_MACHINE_DATA_URL,
    OEWS_MACHINE_MIRROR_URL,
    OEWS_MACHINE_SOURCE,
    OEWSSnapshotBuildError,
    _iter_tab_records,
)


OEWS_WAGE_SNAPSHOT_SCHEMA_VERSION = 1


def build_multi_area_wage_snapshot_from_lines(
    lines: Iterable[str],
    *,
    area_codes: Iterable[str],
    source_year: int,
    catalog_rows: Iterable[object],
    area_metadata: Mapping[str, Mapping[str, str]] | None = None,
    source_url: str = OEWS_MACHINE_DATA_URL,
    generated_at: Optional[str] = None,
) -> dict:
    """Build a local median-wage snapshot for explicit areas in one pass.

    Each detailed occupation in ``catalog_rows`` yields one observation
    with nullable ``median_hourly_wage``/``median_annual_wage`` fields.
    A value stays null (never zero, never a placeholder) whenever BLS
    suppresses or omits that specific wage datatype.
    """
    areas = sorted({normalize_area_code(code) for code in area_codes})
    if not areas:
        raise OEWSSnapshotBuildError("At least one OEWS area is required.")

    catalog_by_area_occupation: dict[tuple[str, str], object] = {}
    for item in catalog_rows:
        if item.area_code not in areas or item.source_year != source_year:
            continue
        if getattr(item, "display_level", 3) != 3:
            continue
        catalog_by_area_occupation[(item.area_code, item.occupation_code)] = item

    missing_catalog_areas = [
        area
        for area in areas
        if not any(key[0] == area for key in catalog_by_area_occupation)
    ]
    if missing_catalog_areas:
        raise OEWSSnapshotBuildError(
            "The catalog has no detailed occupations for: "
            + ", ".join(missing_catalog_areas)
        )

    series_index: dict[str, tuple[str, str, str]] = {}
    for (area, occupation_code), item in catalog_by_area_occupation.items():
        area_type = (area_metadata or {}).get(area, {}).get("area_type", "M")
        hourly_series = build_oews_series_id(
            area_code=area,
            occupation_code=occupation_code,
            area_type_code=area_type,
            datatype_code=OEWS_HOURLY_MEDIAN_WAGE_DATATYPE,
        )
        annual_series = build_oews_series_id(
            area_code=area,
            occupation_code=occupation_code,
            area_type_code=area_type,
            datatype_code=OEWS_ANNUAL_MEDIAN_WAGE_DATATYPE,
        )
        series_index[hourly_series] = (area, occupation_code, "hourly")
        series_index[annual_series] = (area, occupation_code, "annual")

    wages: dict[tuple[str, str], dict[str, Optional[float]]] = {
        key: {"median_hourly_wage": None, "median_annual_wage": None}
        for key in catalog_by_area_occupation
    }
    seen = set()
    suppressed_by_area = {area: 0 for area in areas}

    for fields in _iter_tab_records(lines):
        series_id = fields["series_id"]
        if series_id not in series_index or fields["period"] != "A01":
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
                f"Duplicate OEWS wage observation for series {series_id}."
            )
        seen.add(key)
        area, occupation_code, measure = series_index[series_id]
        try:
            value = float(fields["value"])
        except (TypeError, ValueError):
            suppressed_by_area[area] += 1
            continue
        if value < 0:
            suppressed_by_area[area] += 1
            continue
        wages[(area, occupation_code)][
            "median_hourly_wage" if measure == "hourly" else "median_annual_wage"
        ] = value

    observations = []
    for (area, occupation_code), item in catalog_by_area_occupation.items():
        wage = wages[(area, occupation_code)]
        observations.append({
            "area_code": area,
            "occupation_code": occupation_code,
            "occupation_title": item.occupation_title,
            "year": source_year,
            "median_hourly_wage": wage["median_hourly_wage"],
            "median_annual_wage": wage["median_annual_wage"],
            "source": OEWS_MACHINE_SOURCE,
            "catalog_source": item.source,
            "source_url": source_url,
        })

    observations.sort(key=lambda item: (item["area_code"], item["occupation_code"]))
    metadata = {
        area: dict(area_metadata[area])
        for area in areas
        if area_metadata and area in area_metadata
    }
    return {
        "schema_version": OEWS_WAGE_SNAPSHOT_SCHEMA_VERSION,
        "source": OEWS_MACHINE_SOURCE,
        "source_url": source_url,
        "catalog_source": "BLS OEWS time-series catalog",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "source_years": [source_year],
        "areas": areas,
        "area_metadata": metadata,
        "suppressed_or_missing_count": sum(suppressed_by_area.values()),
        "suppressed_or_missing_by_area": suppressed_by_area,
        "observations": observations,
    }


def validate_preserved_wage_area(
    *,
    existing_snapshot: Mapping[str, object],
    replacement_snapshot: Mapping[str, object],
    area_code: str,
) -> None:
    """Refuse a migration that changes an existing area's wage values."""
    area = normalize_area_code(area_code)

    def rows(snapshot: Mapping[str, object]) -> list[dict]:
        return sorted(
            [
                item
                for item in snapshot.get("observations", [])
                if item.get("area_code") == area
            ],
            key=lambda item: item["occupation_code"],
        )

    if rows(existing_snapshot) != rows(replacement_snapshot):
        raise OEWSSnapshotBuildError(
            f"Existing {area} wage observations do not match the "
            "replacement snapshot."
        )


def _write_snapshot_atomically(path: Path, snapshot: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_multi_area_wage_employment_snapshot(
    *,
    area_codes: Iterable[str],
    source_year: int,
    output_path: Path | str,
    catalog_client: Optional[OEWSClient] = None,
    data_url: str = OEWS_MACHINE_DATA_URL,
    timeout: int = 120,
) -> dict:
    """Ingest official OEWS median wage data for explicit areas."""
    areas = sorted({normalize_area_code(code) for code in area_codes})
    client = catalog_client or OEWSClient()
    catalog_rows = []
    for area in areas:
        catalog_rows.extend(
            client.fetch_catalog_detailed_occupations(
                area_code=area,
                source_year=source_year,
            )
        )
    area_metadata = {
        row["area_code"]: {
            "state_code": row["state_code"],
            "area_type": row["areatype_code"],
            "area_name": row["area_name"],
        }
        for row in client._iter_catalog_file("oe.area")
        if row.get("area_code") in areas
    }
    if set(area_metadata) != set(areas):
        missing = sorted(set(areas) - set(area_metadata))
        raise OEWSSnapshotBuildError(
            "Official OEWS area metadata is missing for: "
            + ", ".join(missing)
        )
    response = requests.get(data_url, timeout=timeout, stream=True)
    resolved_data_url = data_url
    if (
        getattr(response, "status_code", 200) == 403
        and data_url == OEWS_MACHINE_DATA_URL
    ):
        resolved_data_url = OEWS_MACHINE_MIRROR_URL
        response = requests.get(
            resolved_data_url,
            timeout=timeout,
            stream=True,
        )
    response.raise_for_status()
    snapshot = build_multi_area_wage_snapshot_from_lines(
        response.iter_lines(decode_unicode=True),
        area_codes=areas,
        source_year=source_year,
        catalog_rows=catalog_rows,
        area_metadata=area_metadata,
        source_url=data_url,
    )
    snapshot["retrieved_from_url"] = resolved_data_url
    _write_snapshot_atomically(Path(output_path), snapshot)
    return snapshot
