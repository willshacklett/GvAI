from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gvai.postlabor.sources.oews import OEWSClient
from gvai.postlabor.sources.oews_snapshot import (
    build_multi_area_employment_snapshot,
    validate_preserved_area,
)


TENNESSEE_STATE_CODE = "47"
DEFAULT_OUTPUT = Path(
    "gvai/postlabor/snapshots/oews/employment_index.json"
)


def area_codes_for_state(client: OEWSClient, state_code: str) -> list[str]:
    state = str(state_code).zfill(2)
    return sorted({
        row["area_code"]
        for row in client._iter_catalog_file("oe.area")
        if row.get("state_code") == state
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an official multi-area OEWS 2025 snapshot."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--state",
        help="Two-digit BLS state code; includes every official OEWS area listed for it.",
    )
    selection.add_argument(
        "--areas",
        nargs="+",
        help="Explicit seven-digit OEWS area codes.",
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    client = OEWSClient()
    area_codes = (
        area_codes_for_state(client, args.state)
        if args.state
        else args.areas
    )
    if not area_codes:
        raise SystemExit("No official OEWS areas matched the requested selection.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{args.output.name}.",
        suffix=".tmp",
        dir=args.output.parent,
    )
    os.close(fd)
    temporary_output = Path(temporary_name)
    try:
        snapshot = build_multi_area_employment_snapshot(
            area_codes=area_codes,
            source_year=args.year,
            output_path=temporary_output,
            catalog_client=client,
        )
        if args.output == DEFAULT_OUTPUT and DEFAULT_OUTPUT.is_file():
            existing = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
            validate_preserved_area(
                existing_snapshot=existing,
                replacement_snapshot=snapshot,
                area_code="0034980",
            )
        os.replace(temporary_output, args.output)
    finally:
        temporary_output.unlink(missing_ok=True)
    print("areas:", len(snapshot["areas"]))
    for area in snapshot["areas"]:
        metadata = snapshot["area_metadata"].get(area, {})
        print(area, metadata.get("area_name", "Unknown area"))
    print("observations:", len(snapshot["observations"]))
    print("totals:", len(snapshot["totals"]))
    print("suppressed_or_missing:", snapshot["suppressed_or_missing_count"])
    print("output:", args.output)
    print("bytes:", args.output.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())