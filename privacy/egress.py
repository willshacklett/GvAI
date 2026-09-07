"""
GVAI Universal Egress Guard v0.1

This module is the single reusable privacy checkpoint placed immediately
before GVAI transmits information to an external AI/model/service.

Private by default.
Provider agnostic.
User/project scoped.
"""

from __future__ import annotations

import os
from typing import Optional

from privacy.router import (
    AuditLog,
    DataClass,
    DestinationClass,
    PrivacyContext,
    PrivacyRouter,
    enforce,
)


_router = PrivacyRouter(
    AuditLog(
        os.getenv(
            "GVAI_PRIVACY_AUDIT_LOG",
            "privacy/audit.jsonl",
        )
    )
)


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def context_from_env(
    *,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    data_class: Optional[str] = None,
    private_build_mode: Optional[bool] = None,
    consent_token: Optional[str] = None,
) -> PrivacyContext:
    """
    Temporary environment-backed context.

    Later this will be replaced/augmented by authenticated user and
    project records from GVAI's application layer.
    """

    resolved_user = (
        user_id
        or os.getenv("GVAI_USER_ID")
        or "anonymous"
    )

    resolved_project = (
        project_id
        or os.getenv("GVAI_PROJECT_ID")
        or "default"
    )

    raw_class = (
        data_class
        or os.getenv("GVAI_DATA_CLASS")
        or "private"
    ).strip().lower()

    try:
        resolved_class = DataClass(raw_class)
    except ValueError:
        # Unknown classification fails safely as private.
        resolved_class = DataClass.PRIVATE

    if private_build_mode is None:
        resolved_private_mode = _truthy(
            os.getenv("GVAI_PRIVATE_BUILD_MODE", "0")
        )
    else:
        resolved_private_mode = bool(private_build_mode)

    resolved_consent = (
        consent_token
        or os.getenv("GVAI_CONSENT_TOKEN")
        or None
    )

    return PrivacyContext(
        user_id=resolved_user,
        project_id=resolved_project,
        data_class=resolved_class,
        private_build_mode=resolved_private_mode,
        consent_token=resolved_consent,
    )


def authorize_external_model(
    payload: str,
    *,
    provider: str,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    data_class: Optional[str] = None,
    private_build_mode: Optional[bool] = None,
    consent_token: Optional[str] = None,
):
    """
    MUST be called immediately before transmitting content
    to OpenAI, xAI, Anthropic, or any future external model.
    """

    ctx = context_from_env(
        user_id=user_id,
        project_id=project_id,
        data_class=data_class,
        private_build_mode=private_build_mode,
        consent_token=consent_token,
    )

    decision = enforce(
        _router,
        ctx,
        DestinationClass.EXTERNAL_MODEL,
        payload=payload,
    )

    return {
        "allowed": True,
        "provider": provider,
        "user_id": ctx.user_id,
        "project_id": ctx.project_id,
        "data_class": ctx.data_class.value,
        "private_build_mode": ctx.private_build_mode,
        "reason": decision.reason,
    }


def authorize_external_write(
    payload: str,
    *,
    destination: str,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    data_class: Optional[str] = None,
    private_build_mode: Optional[bool] = None,
    consent_token: Optional[str] = None,
):
    """
    Gate writes to external non-model services.
    """

    ctx = context_from_env(
        user_id=user_id,
        project_id=project_id,
        data_class=data_class,
        private_build_mode=private_build_mode,
        consent_token=consent_token,
    )

    decision = enforce(
        _router,
        ctx,
        DestinationClass.EXTERNAL_WRITE,
        payload=payload,
    )

    return {
        "allowed": True,
        "destination": destination,
        "user_id": ctx.user_id,
        "project_id": ctx.project_id,
        "reason": decision.reason,
    }


def authorize_world_read(
    *,
    source: str,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
):
    """
    Public information may enter GVAI even while Private Build Mode
    protects private information from leaving.
    """

    ctx = context_from_env(
        user_id=user_id,
        project_id=project_id,
    )

    decision = enforce(
        _router,
        ctx,
        DestinationClass.WORLD_READ,
        payload="",
    )

    return {
        "allowed": True,
        "source": source,
        "reason": decision.reason,
    }
