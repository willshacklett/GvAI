"""Country-scoped live-job orchestration for the Laborers workspace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence
import os

from gvai.postlabor.labor_providers import (
    LiveJobsProvider,
    NormalizedJobOpening,
    OccupationReference,
    ProviderMetadata,
    PublishedCompensation,
    live_jobs_provider_for_country,
)


LIVE_JOB_STATUSES = (
    "available_with_results",
    "available_zero_results",
    "provider_unavailable",
    "unsupported_country",
    "provider_failure",
)
DEFAULT_RESULT_LIMIT = 25


@dataclass(frozen=True)
class PublicJobSearchContext:
    country_code: str
    occupation_code: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius: float | None = None

    def __post_init__(self) -> None:
        normalized = str(self.country_code or "").strip().upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country_code must be a two-letter ISO country code.")
        object.__setattr__(self, "country_code", normalized)


@dataclass(frozen=True)
class LiveJobsResult:
    status: str
    country_code: str
    provider: str | None
    attribution: str | None
    provider_registered: bool = False
    openings: tuple[NormalizedJobOpening, ...] = ()
    reason: str | None = None
    error_type: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "country_code": self.country_code,
            "provider": self.provider,
            "attribution": self.attribution,
            "provider_registered": self.provider_registered,
            "openings": [opening.to_dict() for opening in self.openings],
            "reason": self.reason,
            "error_type": self.error_type,
        }


def _datetime(value: object, field: str) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO datetime.") from exc
    raise ValueError(f"{field} must be an ISO datetime or null.")


def normalize_provider_opening(
    opening: NormalizedJobOpening | Mapping[str, Any],
    *,
    metadata: ProviderMetadata,
    context: PublicJobSearchContext,
) -> NormalizedJobOpening:
    """Validate or normalize an adapter result without filling unknowns."""
    if isinstance(opening, NormalizedJobOpening):
        if opening.country_code != context.country_code:
            raise ValueError("provider opening country does not match the request.")
        return opening
    if not isinstance(opening, Mapping):
        raise ValueError("provider opening must be a mapping or NormalizedJobOpening.")

    raw_occupation = opening.get("occupation")
    occupation = None
    if raw_occupation is not None:
        if not isinstance(raw_occupation, Mapping):
            raise ValueError("occupation must be a mapping or null.")
        occupation = OccupationReference(**dict(raw_occupation))

    raw_compensation = opening.get("compensation")
    compensation = None
    if raw_compensation is not None:
        if not isinstance(raw_compensation, Mapping):
            raise ValueError("compensation must be a mapping or null.")
        compensation = PublishedCompensation(**dict(raw_compensation))

    return NormalizedJobOpening(
        provider=str(opening.get("provider") or metadata.provider),
        provider_job_id=str(opening.get("provider_job_id") or ""),
        title=str(opening.get("title") or ""),
        employer=opening.get("employer"),
        location=opening.get("location"),
        country_code=str(opening.get("country_code") or context.country_code),
        retrieved_at=_datetime(opening.get("retrieved_at"), "retrieved_at") or datetime.now().astimezone(),
        source_attribution=str(opening.get("source_attribution") or metadata.attribution),
        apply_url=str(opening.get("apply_url") or ""),
        occupation=occupation,
        employment_type=opening.get("employment_type"),
        compensation=compensation,
        remote_or_hybrid=opening.get("remote_or_hybrid"),
        posted_at=_datetime(opening.get("posted_at"), "posted_at"),
    )


class LiveJobsRegistry:
    """Registry for authorized adapters, keyed by their country boundary."""

    def __init__(
        self,
        providers: Sequence[LiveJobsProvider] = (),
        *,
        capability_registry: "GlobalProviderRegistry | None" = None,
    ) -> None:
        self._providers = {
            provider.metadata.country_code.upper(): provider
            for provider in providers
        }
        self._capability_registry = capability_registry

    def provider_for_country(self, country_code: str) -> LiveJobsProvider | None:
        return self._providers.get(country_code.upper())

    def search(
        self,
        context: PublicJobSearchContext,
        *,
        occupation: OccupationReference | None = None,
    ) -> LiveJobsResult:
        metadata = live_jobs_provider_for_country(context.country_code)
        if metadata is None:
            return LiveJobsResult(
                status="unsupported_country",
                country_code=context.country_code,
                provider=None,
                attribution=None,
                reason=f"No labor provider is configured for {context.country_code}; U.S. sources were not substituted.",
            )

        provider = self.provider_for_country(context.country_code)
        if provider is None:
            return LiveJobsResult(
                status="provider_unavailable",
                country_code=context.country_code,
                provider=metadata.provider,
                attribution=metadata.attribution,
                provider_registered=False,
                reason="Live job openings are not available from a configured provider for this region yet.",
            )
        if hasattr(provider, "configured") and not provider.configured:
            return LiveJobsResult(
                status="provider_unavailable",
                country_code=context.country_code,
                provider=provider.metadata.provider,
                attribution=provider.metadata.attribution,
                provider_registered=False,
                reason="Live job openings are not available from a configured provider for this region yet.",
            )

        malformed_records = 0
        try:
            raw_openings = provider.list_openings(
                occupation=occupation,
                country_code=context.country_code,
                location=context.location,
                latitude=context.latitude,
                longitude=context.longitude,
                radius=context.radius,
            )
            openings = []
            seen = set()
            result_limit = max(1, min(int(os.getenv("GVAI_LIVE_JOBS_RESULT_LIMIT", str(DEFAULT_RESULT_LIMIT))), 100))
            for raw_opening in raw_openings:
                try:
                    normalized = normalize_provider_opening(
                        raw_opening,
                        metadata=provider.metadata,
                        context=context,
                    )
                except (TypeError, ValueError):
                    malformed_records += 1
                    continue
                key = (normalized.provider, normalized.provider_job_id)
                if key not in seen:
                    seen.add(key)
                    openings.append(normalized)
                    if len(openings) >= result_limit:
                        break
            if malformed_records and not openings:
                raise ValueError("provider returned only malformed job records")
        except Exception as exc:
            if self._capability_registry is not None:
                self._capability_registry.record_failure(
                    context.country_code, provider.metadata.provider, "live_job_openings"
                )
            return LiveJobsResult(
                status="provider_failure",
                country_code=context.country_code,
                provider=provider.metadata.provider,
                attribution=provider.metadata.attribution,
                provider_registered=True,
                reason="The configured live jobs provider failed or returned malformed data.",
                error_type=type(exc).__name__,
            )

        if self._capability_registry is not None:
            self._capability_registry.record_success(
                context.country_code, provider.metadata.provider, "live_job_openings"
            )
        return LiveJobsResult(
            status=("available_with_results" if openings else "available_zero_results"),
            country_code=context.country_code,
            provider=provider.metadata.provider,
            attribution=provider.metadata.attribution,
            provider_registered=True,
            openings=tuple(openings),
        )


from gvai.postlabor.provider_registry import GlobalProviderRegistry, ProviderRegistration
from gvai.postlabor.usajobs_provider import USAJOBS_METADATA, USAJobsProvider


_usajobs_provider = USAJobsProvider()

DEFAULT_PROVIDER_REGISTRY = GlobalProviderRegistry([
    ProviderRegistration(
        country_code=USAJOBS_METADATA.country_code,
        provider=USAJOBS_METADATA.provider,
        capability="live_job_openings",
        priority=1,
        attribution=USAJOBS_METADATA.attribution,
        adapter=_usajobs_provider,
    ),
])

DEFAULT_LIVE_JOBS_REGISTRY = LiveJobsRegistry(
    [_usajobs_provider] if _usajobs_provider.configured else [],
    capability_registry=DEFAULT_PROVIDER_REGISTRY,
)