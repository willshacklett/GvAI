from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional

import requests

from gvai.postlabor.sources.bls import (
    BLSClient,
)


OEWS_EMPLOYMENT_DATATYPE = "01"
OEWS_TOTAL_INDUSTRY = "000000"
OEWS_ALL_OCCUPATIONS = "00-0000.00"
OEWS_SOURCE = "BLS Public Data API v2"
OEWS_CATALOG_SOURCE = "BLS OEWS time-series catalog"
OEWS_CATALOG_BASE_URL = (
    "https://download.bls.gov/pub/time.series/oe"
)
OEWS_CATALOG_MIRROR_BASE_URL = (
    "https://downloadt.bls.gov/pub/time.series/oe"
)
OEWS_API_BATCH_SIZE = 50
OEWS_CATALOG_CACHE_SCHEMA_VERSION = 2
OEWS_EMPLOYMENT_CACHE_SCHEMA_VERSION = 1
OEWS_DEFAULT_CACHE_PATH = Path(
    "data/oews/catalog_index.json"
)
OEWS_DEFAULT_EMPLOYMENT_CACHE_PATH = Path(
    "data/oews/employment_index.json"
)


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


def format_oews_soc_code(
    occupation_code: str,
) -> str:
    """Convert the catalog's six-digit SOC field to O*NET-SOC form."""
    value = normalize_soc_code(occupation_code)
    return f"{value[:2]}-{value[2:]}.00"


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
    source: str = OEWS_SOURCE
    occupation_title: Optional[str] = None
    catalog_source: Optional[str] = None

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
            "source":
                self.source,
            "occupation_title":
                self.occupation_title,
            "catalog_source":
                self.catalog_source,
        }


@dataclass(frozen=True)
class OEWSOccupationSeries:
    area_code: str
    occupation_code: str
    occupation_title: str
    series_id: str
    datatype_code: str
    industry_code: str
    source_year: int
    source: str = OEWS_CATALOG_SOURCE

    def to_dict(self):
        return {
            "area_code": self.area_code,
            "occupation_code": self.occupation_code,
            "occupation_title": self.occupation_title,
            "series_id": self.series_id,
            "datatype_code": self.datatype_code,
            "industry_code": self.industry_code,
            "source_year": self.source_year,
            "source": self.source,
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
        *,
        catalog_base_url: str = OEWS_CATALOG_BASE_URL,
        catalog_timeout: int = 30,
        catalog_cache_path: Path | str = OEWS_DEFAULT_CACHE_PATH,
        employment_cache_path: Path | str = (
            OEWS_DEFAULT_EMPLOYMENT_CACHE_PATH
        ),
    ) -> None:
        self.bls_client = (
            bls_client
            or BLSClient()
        )
        self.catalog_base_url = catalog_base_url.rstrip("/")
        self.catalog_timeout = catalog_timeout
        self.catalog_cache_path = Path(catalog_cache_path)
        self.employment_cache_path = Path(employment_cache_path)

    def fetch_total_employment(
        self,
        *,
        area_code: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> Optional[OEWSEmploymentEstimate]:
        """
        Fetch OEWS All Occupations employment for an area.

        This is used as the reference employment
        denominator for regional STEX coverage.
        """
        rows = self.fetch_employment(
            area_code=area_code,
            occupation_codes=[
                OEWS_ALL_OCCUPATIONS,
            ],
            start_year=start_year,
            end_year=end_year,
        )

        if not rows:
            return None

        return rows[0]

    def fetch_regional_employment(
        self,
        *,
        area_code: str,
        occupation_codes: Iterable[str],
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> tuple[
        Optional[OEWSEmploymentEstimate],
        List[OEWSEmploymentEstimate],
    ]:
        """
        Fetch an area's denominator and supplied detailed occupations.

        The OEWS time-series API accepts known series IDs but does not
        enumerate the detailed SOC universe. Callers must supply that
        universe from an authoritative source rather than guessing codes.
        """
        total = self.fetch_total_employment(
            area_code=area_code,
            start_year=start_year,
            end_year=end_year,
        )
        occupations = self.fetch_employment(
            area_code=area_code,
            occupation_codes=occupation_codes,
            start_year=start_year,
            end_year=end_year,
        )

        return total, occupations

    def fetch_catalog_detailed_occupations(
        self,
        *,
        area_code: str,
        source_year: Optional[int] = None,
    ) -> List[OEWSOccupationSeries]:
        """Enumerate level-3 detailed OEWS occupations for an area.

        Runtime lookups read the compact local index. The remote BLS catalog
        is populated only by refresh_catalog_cache(). Aggregate SOC groups
        are excluded during refresh using the catalog's display_level field.
        """
        area = normalize_area_code(area_code)
        cache = self._load_catalog_cache()
        applicable_year = source_year
        if applicable_year is None and cache["areas"]:
            applicable_year = max(
                int(vintage["end_year"])
                for area_vintages in cache["areas"].values()
                for vintage in area_vintages
            )
        results = []
        for vintage in cache["areas"].get(area, []):
            if applicable_year is not None:
                if not (
                    vintage["begin_year"]
                    <= applicable_year
                    <= vintage["end_year"]
                ):
                    continue
            for occupation in vintage["occupations"]:
                results.append(
                    OEWSOccupationSeries(
                        area_code=area,
                        occupation_code=occupation,
                        occupation_title=cache["occupations"][
                            normalize_soc_code(occupation)
                        ],
                        series_id=build_oews_series_id(
                            area_code=area,
                            occupation_code=occupation,
                        ),
                        datatype_code=OEWS_EMPLOYMENT_DATATYPE,
                        industry_code=OEWS_TOTAL_INDUSTRY,
                        source_year=applicable_year,
                        source=cache["source"],
                    )
                )

        results.sort(key=lambda item: item.occupation_code)
        return results

    def refresh_catalog_cache(self) -> int:
        """Download and rebuild the compact local OEWS occupation index."""
        occupations = self._fetch_catalog_file("oe.occupation")
        detailed = {
            fields["occupation_code"]: fields["occupation_name"]
            for fields in occupations
            if fields.get("display_level") == "3"
            and fields.get("occupation_code") != "000000"
        }
        areas = {}
        for fields in self._iter_catalog_file("oe.series"):
            occupation = fields.get("occupation_code")
            if (
                occupation not in detailed
                or fields.get("industry_code") != OEWS_TOTAL_INDUSTRY
                or fields.get("datatype_code") != OEWS_EMPLOYMENT_DATATYPE
            ):
                continue
            try:
                begin_year = int(fields["begin_year"])
                end_year = int(fields["end_year"])
            except (KeyError, TypeError, ValueError):
                continue
            area = fields.get("area_code")
            if not area:
                continue
            area_vintages = areas.setdefault(area, [])
            vintage = next(
                (
                    item for item in area_vintages
                    if item["begin_year"] == begin_year
                    and item["end_year"] == end_year
                ),
                None,
            )
            if vintage is None:
                vintage = {
                    "begin_year": begin_year,
                    "end_year": end_year,
                    "occupations": [],
                }
                area_vintages.append(vintage)
            code = format_oews_soc_code(occupation)
            if code not in vintage["occupations"]:
                vintage["occupations"].append(code)
        for area_vintages in areas.values():
            for vintage in area_vintages:
                vintage["occupations"].sort()
            area_vintages.sort(
                key=lambda item: (
                    item["begin_year"],
                    item["end_year"],
                )
            )
        payload = {
            "schema_version": OEWS_CATALOG_CACHE_SCHEMA_VERSION,
            "source": OEWS_CATALOG_SOURCE,
            "datatype_code": OEWS_EMPLOYMENT_DATATYPE,
            "industry_code": OEWS_TOTAL_INDUSTRY,
            "occupations": {
                code: title
                for code, title in sorted(
                    detailed.items()
                )
            },
            "areas": areas,
        }
        self.catalog_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_cache_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return sum(
            len(vintage["occupations"])
            for area_vintages in areas.values()
            for vintage in area_vintages
        )

    def _load_catalog_cache(self) -> Mapping[str, object]:
        try:
            payload = json.loads(
                self.catalog_cache_path.read_text(encoding="utf-8")
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "OEWS catalog cache is missing; run "
                "refresh_catalog_cache() before regional lookup."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "OEWS catalog cache is unreadable; refresh it explicitly."
            ) from exc
        if payload.get("schema_version") != OEWS_CATALOG_CACHE_SCHEMA_VERSION:
            raise RuntimeError(
                "OEWS catalog cache is stale or incompatible; "
                "refresh it explicitly."
            )
        if not isinstance(payload.get("occupations"), dict) or not isinstance(
            payload.get("areas"), dict
        ):
            raise RuntimeError(
                "OEWS catalog cache has no valid records; refresh it."
            )
        return payload

    def refresh_employment_cache(
        self,
        *,
        area_code: str,
        source_year: int,
    ) -> int:
        """Fetch one area's OEWS observations and persist them locally.

        This is an explicit ingestion operation. It may use the BLS API, but
        runtime regional lookups never call it implicitly.
        """
        area = normalize_area_code(area_code)
        series_rows = self.fetch_catalog_detailed_occupations(
            area_code=area,
            source_year=source_year,
        )
        if not series_rows:
            raise ValueError(
                "No detailed OEWS catalog universe is available for "
                "the requested area and year."
            )
        total = self.fetch_total_employment(
            area_code=area,
            start_year=source_year,
            end_year=source_year,
        )
        rows = self.fetch_employment(
            area_code=area,
            occupation_codes=[item.occupation_code for item in series_rows],
            start_year=source_year,
            end_year=source_year,
            occupation_titles={
                item.occupation_code: item.occupation_title
                for item in series_rows
            },
        )
        payload = self._load_employment_cache(allow_missing=True)
        observations = [
            item.to_dict() | {
                "catalog_source": OEWS_CATALOG_SOURCE,
            }
            for item in rows
        ]
        payload["observations"] = [
            item for item in payload["observations"]
            if not (
                item["area_code"] == area
                and int(item["year"]) == source_year
            )
        ] + observations
        payload["observations"].sort(
            key=lambda item: (
                item["area_code"],
                item["year"],
                item["occupation_code"],
            )
        )
        if total is not None:
            payload["totals"] = [
                item for item in payload["totals"]
                if not (
                    item["area_code"] == area
                    and int(item["year"]) == source_year
                )
            ] + [total.to_dict()]
        self.employment_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.employment_cache_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return len(rows)

    def fetch_catalog_regional_employment(
        self,
        *,
        area_code: str,
        source_year: Optional[int] = None,
    ) -> tuple[
        Optional[OEWSEmploymentEstimate],
        List[OEWSEmploymentEstimate],
    ]:
        """Read the official denominator and details from local snapshots."""
        area = normalize_area_code(area_code)
        cache = self._load_employment_cache()
        year = source_year
        if year is None:
            years = {
                int(item["year"])
                for item in cache["observations"]
                if item["area_code"] == area
            }
            years.update(
                int(item["year"])
                for item in cache["totals"]
                if item["area_code"] == area
            )
            year = max(years) if years else None
        if year is None:
            raise RuntimeError(
                "OEWS employment cache has no refreshed data for area "
                f"{area}; run refresh_employment_cache()."
            )
        total = next(
            (
                self._estimate_from_cache(item)
                for item in cache["totals"]
                if item["area_code"] == area
                and int(item["year"]) == year
            ),
            None,
        )
        if total is None:
            raise RuntimeError(
                "OEWS employment denominator is unavailable or stale for "
                f"area {area}, year {year}; refresh explicitly."
            )
        rows = [
            self._estimate_from_cache(item)
            for item in cache["observations"]
            if item["area_code"] == area
            and int(item["year"]) == year
        ]
        return total, rows

    def _load_employment_cache(
        self,
        *,
        allow_missing: bool = False,
    ) -> Mapping[str, object]:
        if not self.employment_cache_path.exists():
            if allow_missing:
                return {
                    "schema_version": OEWS_EMPLOYMENT_CACHE_SCHEMA_VERSION,
                    "source": OEWS_SOURCE,
                    "observations": [],
                    "totals": [],
                }
            raise RuntimeError(
                "OEWS employment cache is missing; run "
                "refresh_employment_cache() explicitly."
            )
        try:
            payload = json.loads(
                self.employment_cache_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "OEWS employment cache is unreadable; refresh it explicitly."
            ) from exc
        if payload.get("schema_version") != OEWS_EMPLOYMENT_CACHE_SCHEMA_VERSION:
            raise RuntimeError(
                "OEWS employment cache is stale or incompatible; "
                "refresh it explicitly."
            )
        if not isinstance(payload.get("observations"), list) or not isinstance(
            payload.get("totals"), list
        ):
            raise RuntimeError(
                "OEWS employment cache is invalid; refresh it explicitly."
            )
        return payload

    @staticmethod
    def _estimate_from_cache(item: Mapping[str, object]):
        return OEWSEmploymentEstimate(
            area_code=str(item["area_code"]),
            occupation_code=str(item["occupation_code"]),
            series_id=str(item["series_id"]),
            year=int(item["year"]),
            employment=float(item["employment"]),
            source=str(item.get("source") or OEWS_SOURCE),
            occupation_title=item.get("occupation_title"),
            catalog_source=item.get("catalog_source"),
        )

    def _fetch_catalog_file(
        self,
        filename: str,
    ) -> List[Mapping[str, str]]:
        return list(self._iter_catalog_file(filename))

    def _iter_catalog_file(
        self,
        filename: str,
    ):
        response = requests.get(
            f"{self.catalog_base_url}/{filename}",
            timeout=self.catalog_timeout,
            stream=True,
        )
        if (
            getattr(response, "status_code", 200) == 403
            and self.catalog_base_url == OEWS_CATALOG_BASE_URL
        ):
            response = requests.get(
                f"{OEWS_CATALOG_MIRROR_BASE_URL}/{filename}",
                timeout=self.catalog_timeout,
                stream=True,
            )
        response.raise_for_status()

        if hasattr(response, "iter_lines"):
            lines = response.iter_lines(decode_unicode=True)
        else:
            lines = iter(response.text.splitlines())

        try:
            header_line = next(lines)
        except StopIteration:
            return

        if isinstance(header_line, bytes):
            header_line = header_line.decode("utf-8")
        headers = [item.strip() for item in header_line.split("\t")]
        for line in lines:
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            values = line.split("\t")
            if len(values) != len(headers):
                continue
            yield {
                header: value.strip()
                for header, value in zip(headers, values)
            }

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
        occupation_titles: Optional[Mapping[str, str]] = None,
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

        series = []
        series_ids = list(series_map)
        for offset in range(0, len(series_ids), OEWS_API_BATCH_SIZE):
            series.extend(
                self.bls_client.fetch_series(
                    series_ids[offset:offset + OEWS_API_BATCH_SIZE],
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
                    source=OEWS_SOURCE,
                    occupation_title=(
                        (occupation_titles or {}).get(
                            original_code
                        )
                    ),
                )
            )

        return results
