from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_STEX_DATA_ROOT = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "stex"
    / "occupations"
)

_ONET_SOC_RE = re.compile(r"^\d{2}-\d{4}\.\d{2}$")


class STEXProfileNotFound(FileNotFoundError):
    pass


class InvalidSTEXOccupationCode(ValueError):
    pass


def normalize_occupation_code(code: str) -> str:
    code = (code or "").strip()

    if not _ONET_SOC_RE.fullmatch(code):
        raise InvalidSTEXOccupationCode(
            "Occupation code must use O*NET-SOC format "
            "such as 37-2021.00."
        )

    return code


def occupation_profile_path(
    code: str,
    data_root: Path | None = None,
) -> Path:
    code = normalize_occupation_code(code)

    root = (
        Path(data_root)
        if data_root is not None
        else DEFAULT_STEX_DATA_ROOT
    )

    safe_code = code.replace(".", "_")

    return root / f"{safe_code}.stex.json"


def load_occupation_stex_profile(
    code: str,
    data_root: Path | None = None,
) -> dict[str, Any]:
    path = occupation_profile_path(
        code=code,
        data_root=data_root,
    )

    if not path.is_file():
        raise STEXProfileNotFound(
            f"No STEX occupation profile exists for {code}."
        )

    payload = json.loads(path.read_text())

    if payload.get("occupation_code") != code:
        raise ValueError(
            "STEX profile occupation code does not match "
            "the requested occupation."
        )

    return payload
