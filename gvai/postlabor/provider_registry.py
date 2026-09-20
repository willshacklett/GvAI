"""Global Job Provider Coverage Registry V1.

Represents, per country and capability, which authorized live-job adapters
are registered and their current runtime state. This registry never fetches
jobs, never scrapes, never scores or ranks providers by quality or worker
fit, and never exposes adapter credentials. It only reports whether an
adapter is registered, authorized (configured), and recently healthy.

Two levels of state are reported:

- Per-provider state (`ProviderRuntimeState`): "configured" (registered and
  authorized), "authorization_required" (registered but missing
  credentials), or "temporarily_unavailable" (registered, authorized, but
  recently failed and inside its cooldown window).
- Per-country/capability aggregate state (`CountryCapabilityState`):
  "available" (at least one configured provider), "temporarily_unavailable"
  (registered providers exist but none are currently configured-and-healthy,
  and at least one is in cooldown), "authorization_required" (registered
  providers exist but none are configured or in cooldown), or "unsupported"
  (no provider is registered for this country/capability at all).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal, Mapping, Sequence

from gvai.postlabor.labor_providers import EvidenceCapability


ProviderRuntimeState = Literal[
    "configured", "authorization_required", "temporarily_unavailable"
]
CountryCapabilityState = Literal[
    "available", "authorization_required", "temporarily_unavailable", "unsupported"
]

DEFAULT_COOLDOWN_SECONDS = 300.0


@dataclass(frozen=True)
class ProviderRegistration:
    """Static, non-secret declaration of an adapter's participation.

    `priority` orders provider selection only; it never implies job quality
    or worker fit. `adapter` must expose a `configured` attribute/property;
    adapters without one are treated as always configured.
    """

    country_code: str
    provider: str
    capability: EvidenceCapability
    priority: int
    attribution: str
    adapter: object

    def __post_init__(self) -> None:
        normalized = str(self.country_code or "").strip().upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country_code must be a two-letter ISO country code.")
        if not str(self.provider).strip():
            raise ValueError("provider is required.")
        if not str(self.attribution).strip():
            raise ValueError("attribution is required.")
        object.__setattr__(self, "country_code", normalized)

    @property
    def is_configured(self) -> bool:
        return bool(getattr(self.adapter, "configured", True))


@dataclass(frozen=True)
class ProviderCapabilityStatus:
    """Secret-safe status for a single registered provider."""

    country_code: str
    provider: str
    capability: EvidenceCapability
    priority: int
    attribution: str
    state: ProviderRuntimeState
    reason: str | None
    supported_search_filters: tuple[str, ...] = ()
    search_filter_options: Mapping[str, tuple[Mapping[str, str], ...]] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "country_code": self.country_code,
            "provider": self.provider,
            "capability": self.capability,
            "priority": self.priority,
            "attribution": self.attribution,
            "state": self.state,
            "reason": self.reason,
            "supported_search_filters": list(self.supported_search_filters),
            "search_filter_options": self.search_filter_options or {},
        }


@dataclass(frozen=True)
class CapabilityReport:
    """Secret-safe, country-scoped capability summary across providers."""

    country_code: str
    capability: EvidenceCapability
    state: CountryCapabilityState
    providers: tuple[ProviderCapabilityStatus, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "country_code": self.country_code,
            "capability": self.capability,
            "state": self.state,
            "providers": [status.to_dict() for status in self.providers],
        }


class GlobalProviderRegistry:
    """Country/provider capability registry for live-job coverage.

    Supports multiple providers per country and providers spanning multiple
    countries. It never fetches jobs and never exposes adapter credentials.
    """

    def __init__(
        self,
        registrations: Sequence[ProviderRegistration] = (),
        *,
        cooldown_seconds: float | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._registrations: list[ProviderRegistration] = list(registrations)
        self._cooldown_seconds = (
            cooldown_seconds
            if cooldown_seconds is not None
            else self._env_float(
                "GVAI_PROVIDER_UNAVAILABLE_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_SECONDS
            )
        )
        self._clock = clock
        self._failed_until: dict[tuple[str, str, str], datetime] = {}

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _key(
        country_code: str, provider: str, capability: EvidenceCapability
    ) -> tuple[str, str, str]:
        return (str(country_code).strip().upper(), provider, capability)

    def record_failure(
        self, country_code: str, provider: str, capability: EvidenceCapability
    ) -> None:
        key = self._key(country_code, provider, capability)
        self._failed_until[key] = self._clock() + timedelta(seconds=self._cooldown_seconds)

    def record_success(
        self, country_code: str, provider: str, capability: EvidenceCapability
    ) -> None:
        key = self._key(country_code, provider, capability)
        self._failed_until.pop(key, None)

    def _is_temporarily_unavailable(self, registration: ProviderRegistration) -> bool:
        key = self._key(registration.country_code, registration.provider, registration.capability)
        marked_until = self._failed_until.get(key)
        if marked_until is None:
            return False
        if self._clock() >= marked_until:
            self._failed_until.pop(key, None)
            return False
        return True

    def providers_for(
        self, country_code: str, capability: EvidenceCapability
    ) -> list[ProviderRegistration]:
        normalized = str(country_code or "").strip().upper()
        matches = [
            registration
            for registration in self._registrations
            if registration.country_code == normalized
            and registration.capability == capability
        ]
        return sorted(matches, key=lambda registration: registration.priority)

    def provider_status(self, registration: ProviderRegistration) -> ProviderCapabilityStatus:
        if self._is_temporarily_unavailable(registration):
            state: ProviderRuntimeState = "temporarily_unavailable"
            reason = f"{registration.provider} recently failed and is temporarily unavailable."
        elif not registration.is_configured:
            state = "authorization_required"
            reason = f"{registration.provider} is registered but not yet authorized (missing credentials)."
        else:
            state = "configured"
            reason = None
        return ProviderCapabilityStatus(
            country_code=registration.country_code,
            provider=registration.provider,
            capability=registration.capability,
            priority=registration.priority,
            attribution=registration.attribution,
            state=state,
            reason=reason,
            supported_search_filters=tuple(sorted(
                getattr(registration.adapter, "supported_search_filters", ())
            )),
            search_filter_options=getattr(registration.adapter, "search_filter_options", {}),
        )

    def capability_report(
        self, country_code: str, capability: EvidenceCapability
    ) -> CapabilityReport:
        normalized = str(country_code or "").strip().upper()
        registrations = self.providers_for(normalized, capability)
        if not registrations:
            return CapabilityReport(
                country_code=normalized,
                capability=capability,
                state="unsupported",
                providers=(),
            )

        statuses = tuple(self.provider_status(registration) for registration in registrations)
        if any(status.state == "configured" for status in statuses):
            aggregate: CountryCapabilityState = "available"
        elif any(status.state == "temporarily_unavailable" for status in statuses):
            aggregate = "temporarily_unavailable"
        else:
            aggregate = "authorization_required"

        return CapabilityReport(
            country_code=normalized,
            capability=capability,
            state=aggregate,
            providers=statuses,
        )
