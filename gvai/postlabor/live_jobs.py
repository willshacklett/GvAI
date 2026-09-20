"""Country-scoped live-job orchestration for the Laborers workspace."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Mapping, Sequence
import os
from urllib.parse import urlsplit, urlunsplit

from gvai.postlabor.labor_providers import (
    LiveJobsProvider,
    NormalizedJobOpening,
    OccupationReference,
    ProviderJobReference,
    ProviderMetadata,
    PublishedCompensation,
    live_jobs_provider_for_country,
)


LIVE_JOB_STATUSES = (
    "available_with_results",
    "available_zero_results",
    "authorization_required",
    "unsupported_filters",
    "provider_unavailable",
    "temporarily_unavailable",
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
    remote_only: bool | None = None
    schedule_type_code: str | None = None
    posted_within_days: int | None = None

    def __post_init__(self) -> None:
        normalized = str(self.country_code or "").strip().upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country_code must be a two-letter ISO country code.")
        if self.radius is not None and self.radius <= 0:
            raise ValueError("radius must be greater than zero.")
        if self.posted_within_days is not None and not 0 <= self.posted_within_days <= 60:
            raise ValueError("posted_within_days must be between 0 and 60.")
        object.__setattr__(self, "country_code", normalized)


@dataclass(frozen=True)
class LiveJobsResult:
    status: str
    country_code: str
    provider: str | None
    attribution: str | None
    provider_registered: bool = False
    openings: tuple[NormalizedJobOpening, ...] = ()
    providers: tuple[str, ...] = ()
    provider_failures: tuple[dict[str, str], ...] = ()
    unsupported_filters: tuple[str, ...] = ()
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
            "providers": list(self.providers),
            "provider_failures": list(self.provider_failures),
            "unsupported_filters": list(self.unsupported_filters),
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

    raw_references = opening.get("provider_references") or ()
    provider_references = tuple(
        reference if isinstance(reference, ProviderJobReference)
        else ProviderJobReference(**dict(reference))
        for reference in raw_references
    )

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
        provider_references=provider_references,
    )


def _canonical_source_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def _merge_provider_reference(
    opening: NormalizedJobOpening,
    duplicate: NormalizedJobOpening,
) -> NormalizedJobOpening:
    references = list(opening.provider_references)
    existing = {(item.provider, item.provider_job_id) for item in references}
    for reference in duplicate.provider_references:
        if (reference.provider, reference.provider_job_id) not in existing:
            references.append(reference)
            existing.add((reference.provider, reference.provider_job_id))
    return replace(opening, provider_references=tuple(references))


class LiveJobsRegistry:
    """Registry for authorized adapters, keyed by their country boundary."""

    def __init__(
        self,
        providers: Sequence[LiveJobsProvider] = (),
        *,
        capability_registry: "GlobalProviderRegistry | None" = None,
    ) -> None:
        self._providers: dict[str, list[LiveJobsProvider]] = {}
        for provider in providers:
            self._providers.setdefault(provider.metadata.country_code.upper(), []).append(provider)
        self._capability_registry = capability_registry

    def provider_for_country(self, country_code: str) -> LiveJobsProvider | None:
        providers = self._providers.get(country_code.upper(), [])
        return providers[0] if providers else None

    def providers_for_country(self, country_code: str) -> tuple[LiveJobsProvider, ...]:
        return tuple(self._providers.get(country_code.upper(), ()))

    def search(
        self,
        context: PublicJobSearchContext,
        *,
        occupation: OccupationReference | None = None,
    ) -> LiveJobsResult:
        metadata = live_jobs_provider_for_country(context.country_code)
        registrations = self._capability_registry.providers_for(
            context.country_code, "live_job_openings"
        ) if self._capability_registry is not None else []
        providers = self.providers_for_country(context.country_code)
        if metadata is None and not registrations and not providers:
            return LiveJobsResult(
                status="unsupported_country",
                country_code=context.country_code,
                provider=None,
                attribution=None,
                reason=f"No labor provider is configured for {context.country_code}; U.S. sources were not substituted.",
            )

        registered = bool(registrations or providers)
        registration_statuses = {
            registration.provider: self._capability_registry.provider_status(registration)
            for registration in registrations
        } if self._capability_registry is not None else {}
        configured_providers = [
            provider for provider in providers
            if not hasattr(provider, "configured") or provider.configured
            if registration_statuses.get(provider.metadata.provider) is None
            or registration_statuses[provider.metadata.provider].state != "temporarily_unavailable"
        ]
        if not configured_providers:
            statuses = list(registration_statuses.values())
            if any(status.state == "temporarily_unavailable" for status in statuses):
                status = "temporarily_unavailable"
                reason = "Registered live jobs providers recently failed and are temporarily unavailable."
            elif any(status.state == "authorization_required" for status in statuses):
                status = "authorization_required"
                reason = "A live jobs provider is registered for this country but requires authorization."
            else:
                status = "provider_unavailable"
                reason = "Live job openings are not available from a configured provider for this region yet."
            return LiveJobsResult(
                status=status,
                country_code=context.country_code,
                provider=metadata.provider if metadata else None,
                attribution=metadata.attribution if metadata else None,
                provider_registered=registered,
                reason=reason,
            )

        requested_filters = {
            name for name, selected in (
                ("location", context.location is not None or context.latitude is not None or context.longitude is not None),
                ("radius", context.radius is not None),
                ("remote_only", context.remote_only is not None),
                ("schedule_type_code", context.schedule_type_code is not None),
                ("posted_within_days", context.posted_within_days is not None),
            ) if selected
        }
        available_providers = []
        unsupported_by_provider: dict[str, set[str]] = {}
        for provider in configured_providers:
            supported = set(getattr(
                provider,
                "supported_search_filters",
                ("location", "radius"),
            ))
            unsupported = requested_filters - supported
            if unsupported:
                unsupported_by_provider[provider.metadata.provider] = unsupported
            else:
                available_providers.append(provider)
        if not available_providers:
            unsupported = sorted(set().union(*unsupported_by_provider.values()))
            return LiveJobsResult(
                status="unsupported_filters",
                country_code=context.country_code,
                provider=None,
                attribution=None,
                provider_registered=True,
                providers=tuple(provider.metadata.provider for provider in configured_providers),
                unsupported_filters=tuple(unsupported),
                reason="No configured provider can honor every selected filter.",
            )

        malformed_records = 0
        openings: list[NormalizedJobOpening] = []
        successful_providers: list[str] = []
        provider_failures: list[dict[str, str]] = []
        seen_provider_ids: set[tuple[str, str]] = set()
        seen_source_urls: dict[str, int] = {}
        result_limit = max(1, min(int(os.getenv("GVAI_LIVE_JOBS_RESULT_LIMIT", str(DEFAULT_RESULT_LIMIT))), 100))
        for provider in available_providers:
            try:
                raw_openings = provider.list_openings(
                    occupation=occupation,
                    country_code=context.country_code,
                    location=context.location,
                    latitude=context.latitude,
                    longitude=context.longitude,
                    radius=context.radius,
                    remote_only=context.remote_only,
                    schedule_type_code=context.schedule_type_code,
                    posted_within_days=context.posted_within_days,
                )
                provider_openings = 0
                provider_malformed = 0
                for raw_opening in raw_openings:
                    try:
                        normalized = normalize_provider_opening(
                            raw_opening,
                            metadata=provider.metadata,
                            context=context,
                        )
                    except (TypeError, ValueError):
                        malformed_records += 1
                        provider_malformed += 1
                        continue
                    provider_openings += 1
                    provider_key = (normalized.provider, normalized.provider_job_id)
                    if provider_key in seen_provider_ids:
                        continue
                    seen_provider_ids.add(provider_key)
                    source_key = _canonical_source_url(normalized.apply_url)
                    if source_key in seen_source_urls:
                        index = seen_source_urls[source_key]
                        openings[index] = _merge_provider_reference(openings[index], normalized)
                    elif len(openings) < result_limit:
                        seen_source_urls[source_key] = len(openings)
                        openings.append(normalized)
                if provider_malformed and not provider_openings:
                    raise ValueError("provider returned only malformed job records")
                successful_providers.append(provider.metadata.provider)
                if self._capability_registry is not None:
                    self._capability_registry.record_success(
                        context.country_code, provider.metadata.provider, "live_job_openings"
                    )
            except Exception as exc:
                provider_failures.append({
                    "provider": provider.metadata.provider,
                    "error_type": type(exc).__name__,
                })
                if self._capability_registry is not None:
                    self._capability_registry.record_failure(
                        context.country_code, provider.metadata.provider, "live_job_openings"
                    )

        if not successful_providers:
            first_provider = available_providers[0]
            return LiveJobsResult(
                status="provider_failure",
                country_code=context.country_code,
                provider=first_provider.metadata.provider,
                attribution=first_provider.metadata.attribution,
                provider_registered=True,
                providers=tuple(provider.metadata.provider for provider in available_providers),
                provider_failures=tuple(provider_failures),
                reason="The configured live jobs provider failed or returned malformed data.",
                error_type=provider_failures[0]["error_type"] if provider_failures else None,
            )

        first_success = next(
            provider for provider in available_providers
            if provider.metadata.provider == successful_providers[0]
        )
        return LiveJobsResult(
            status=("available_with_results" if openings else "available_zero_results"),
            country_code=context.country_code,
            provider=successful_providers[0] if len(successful_providers) == 1 else None,
            attribution=first_success.metadata.attribution if len(successful_providers) == 1 else None,
            provider_registered=True,
            openings=tuple(openings),
            providers=tuple(successful_providers),
            provider_failures=tuple(provider_failures),
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