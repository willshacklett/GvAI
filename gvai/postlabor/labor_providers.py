"""Country-scoped labor evidence and live-jobs provider contracts.

This module is intentionally declarative. It does not match occupations,
infer crosswalks, fetch jobs, rank results, or accept Worker Profile data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal, Mapping, Protocol, Sequence


EvidenceCapability = Literal[
    "occupation_profiles",
    "employment",
    "wages",
    "preparation",
    "structural_exposure",
    "live_job_openings",
]


@dataclass(frozen=True)
class OccupationReference:
    """An occupation identifier in its authoritative provider namespace."""

    country_code: str
    provider: str
    provider_occupation_code: str
    title: str
    international_identifier: str | None = None
    mapping_type: Literal["authoritative", "search_query"] = "authoritative"

    def __post_init__(self) -> None:
        if len(self.country_code) != 2 or not self.country_code.isalpha():
            raise ValueError("country_code must be a two-letter ISO country code.")
        if not self.provider.strip():
            raise ValueError("provider is required.")
        if not self.provider_occupation_code.strip():
            raise ValueError("provider_occupation_code is required.")
        if not self.title.strip():
            raise ValueError("title is required.")
        if self.mapping_type not in {"authoritative", "search_query"}:
            raise ValueError("mapping_type must be authoritative or search_query.")
        object.__setattr__(self, "country_code", self.country_code.upper())

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderMetadata:
    country_code: str
    provider: str
    capabilities: frozenset[EvidenceCapability]
    attribution: str

    def supports(self, capability: EvidenceCapability) -> bool:
        return capability in self.capabilities

    def to_dict(self) -> dict[str, object]:
        return {
            "country_code": self.country_code,
            "provider": self.provider,
            "capabilities": sorted(self.capabilities),
            "attribution": self.attribution,
        }


US_ONET_OEWS_STEX = ProviderMetadata(
    country_code="US",
    provider="us_onet_oews_stex",
    capabilities=frozenset({
        "occupation_profiles",
        "employment",
        "wages",
        "preparation",
        "structural_exposure",
    }),
    attribution="U.S. O*NET, BLS OEWS, and GVAI STEX",
)


US_LIVE_JOBS = ProviderMetadata(
    country_code="US",
    provider="usajobs",
    capabilities=frozenset({"live_job_openings"}),
    attribution="USAJOBS API",
)


def provider_for_country(country_code: str | None) -> ProviderMetadata | None:
    """Return a configured provider only; never fall back across countries."""
    normalized = str(country_code or "US").strip().upper()
    if normalized == "US":
        return US_ONET_OEWS_STEX
    return None


def live_jobs_provider_for_country(country_code: str | None) -> ProviderMetadata | None:
    normalized = str(country_code or "US").strip().upper()
    return US_LIVE_JOBS if normalized == "US" else None


def unavailable_evidence(
    capability: EvidenceCapability,
    country_code: str | None,
) -> dict[str, object]:
    """Describe unsupported evidence without inventing a numeric substitute."""
    normalized = str(country_code or "US").strip().upper()
    provider = provider_for_country(normalized)
    if provider is None:
        reason = (
            f"No labor evidence provider is configured for {normalized}; "
            "U.S. evidence was not substituted."
        )
    else:
        reason = (
            f"{provider.provider} does not currently provide {capability}."
        )
    return {
        "status": "unavailable",
        "value": None,
        "reason": reason,
        "country_code": normalized,
        "provider": provider.provider if provider else None,
    }


@dataclass(frozen=True)
class PublishedCompensation:
    amount: float | None = None
    currency: str | None = None
    interval: Literal["hour", "day", "week", "month", "year"] | None = None
    minimum_amount: float | None = None
    maximum_amount: float | None = None


@dataclass(frozen=True)
class NormalizedJobOpening:
    """A provider-attributed opening; fields absent upstream remain None."""

    provider: str
    provider_job_id: str
    title: str
    employer: str | None
    location: str | None
    country_code: str
    retrieved_at: datetime
    source_attribution: str
    apply_url: str
    occupation: OccupationReference | None = None
    employment_type: str | None = None
    compensation: PublishedCompensation | None = None
    remote_or_hybrid: str | None = None
    posted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.provider_job_id.strip():
            raise ValueError("provider and provider_job_id are required.")
        if not self.title.strip() or not self.country_code.strip():
            raise ValueError("title and country_code are required.")
        if not self.source_attribution.strip() or not self.apply_url.strip():
            raise ValueError("source_attribution and apply_url are required.")
        object.__setattr__(self, "country_code", self.country_code.upper())

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["retrieved_at"] = self.retrieved_at.isoformat()
        result["posted_at"] = self.posted_at.isoformat() if self.posted_at else None
        result["occupation"] = (
            self.occupation.to_dict() if self.occupation else None
        )
        return result


class LiveJobsProvider(Protocol):
    """Authorized live-job adapters must not receive a Worker Profile."""

    metadata: ProviderMetadata

    def list_openings(
        self,
        *,
        occupation: OccupationReference | None = None,
        country_code: str | None = None,
        location: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius: float | None = None,
    ) -> Sequence[NormalizedJobOpening | Mapping[str, Any]]: ...