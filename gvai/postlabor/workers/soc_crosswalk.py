from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


SOC_PATTERN = re.compile(r"^\d{2}-\d{4}(?:\.\d{2})?$")


def normalize_soc(code: str) -> str:
    """
    Normalize SOC/O*NET-SOC codes for lookup.

    Examples:
      15-1252       -> 15-1252
      15-1252.00    -> 15-1252.00
    """
    return str(code or "").strip()


def base_soc(code: str) -> str:
    """
    Convert an O*NET-SOC detailed code to its base SOC where possible.

    15-1252.00 -> 15-1252
    """
    code = normalize_soc(code)

    if "." in code:
        return code.split(".", 1)[0]

    return code


@dataclass(frozen=True)
class SOCCrosswalkRecord:
    onet_soc_code: str
    bls_soc_code: str
    onet_title: str = ""
    bls_title: str = ""


class SOCCrosswalk:
    def __init__(
        self,
        records: Iterable[SOCCrosswalkRecord],
    ) -> None:
        self.records = list(records)

        self._onet_to_bls: Dict[str, List[SOCCrosswalkRecord]] = {}

        for record in self.records:
            self._onet_to_bls.setdefault(
                normalize_soc(record.onet_soc_code),
                [],
            ).append(record)

    def lookup_onet(
        self,
        onet_soc_code: str,
    ) -> List[SOCCrosswalkRecord]:
        code = normalize_soc(onet_soc_code)

        exact = self._onet_to_bls.get(code)

        if exact:
            return list(exact)

        # Safe fallback: base SOC can often match the BLS matrix directly.
        fallback = base_soc(code)

        return [
            record
            for record in self.records
            if base_soc(record.onet_soc_code) == fallback
        ]

    def best_bls_soc(
        self,
        onet_soc_code: str,
    ) -> Optional[str]:
        matches = self.lookup_onet(onet_soc_code)

        if not matches:
            return base_soc(onet_soc_code)

        return matches[0].bls_soc_code
