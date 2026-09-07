"""
GVAI Project Privacy Policy v0.2

Request/project-scoped privacy configuration.

Important:
The application may transport these values through a request, but the
long-term authoritative source MUST be a server-side authenticated
project record. Browser-supplied privacy state must never be trusted
as authority by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from privacy.router import DataClass, PrivacyContext


class ProjectPrivacyMode(str, Enum):
    PRIVATE = "private"
    PUBLIC_DATA_ONLY = "public_data_only"
    STANDARD = "standard"


@dataclass(frozen=True)
class ProjectPrivacyPolicy:
    user_id: str
    project_id: str
    mode: ProjectPrivacyMode = ProjectPrivacyMode.PRIVATE
    consent_token: Optional[str] = None

    def context_for(
        self,
        data_class: DataClass | str = DataClass.PRIVATE,
    ) -> PrivacyContext:

        if isinstance(data_class, str):
            try:
                resolved_class = DataClass(
                    data_class.strip().lower()
                )
            except ValueError:
                resolved_class = DataClass.PRIVATE
        else:
            resolved_class = data_class

        return PrivacyContext(
            user_id=self.user_id,
            project_id=self.project_id,
            data_class=resolved_class,
            private_build_mode=(
                self.mode == ProjectPrivacyMode.PRIVATE
            ),
            consent_token=self.consent_token,
        )


def resolve_project_policy(
    *,
    user_id: Optional[str],
    project_id: Optional[str],
    privacy_mode: Optional[str],
    consent_token: Optional[str] = None,
) -> ProjectPrivacyPolicy:
    """
    Resolve request/application values conservatively.

    Unknown modes fail closed to PRIVATE.
    Missing identities receive non-authoritative placeholders.

    Later this resolver will load the authoritative project policy
    from authenticated server-side storage.
    """

    try:
        mode = ProjectPrivacyMode(
            str(privacy_mode or "private")
            .strip()
            .lower()
        )
    except ValueError:
        mode = ProjectPrivacyMode.PRIVATE

    return ProjectPrivacyPolicy(
        user_id=str(user_id or "anonymous"),
        project_id=str(project_id or "default"),
        mode=mode,
        consent_token=consent_token or None,
    )


def outbound_data_class(
    policy: ProjectPrivacyPolicy,
    *,
    contains_private_project_data: bool,
    explicit_share: bool = False,
) -> DataClass:
    """
    Classify content before external transmission.

    Explicit sharing never becomes valid merely because a caller
    requests it; an actual consent token must also exist.
    """

    if explicit_share:
        return DataClass.EXPLICITLY_SHARED

    if contains_private_project_data:
        return DataClass.PRIVATE

    return DataClass.PUBLIC
