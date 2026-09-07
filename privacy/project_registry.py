from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from privacy.project_policy import (
    ProjectPrivacyMode,
    ProjectPrivacyPolicy,
)

DEFAULT_REGISTRY_PATH = "privacy/projects.json"


class ProjectPolicyRegistry:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(
            path
            or os.getenv("GVAI_PROJECT_REGISTRY")
            or DEFAULT_REGISTRY_PATH
        )

    def _read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "projects": {}}

        try:
            raw = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "projects": {}}

        if not isinstance(raw, dict):
            return {"version": 1, "projects": {}}

        projects = raw.get("projects")
        if not isinstance(projects, dict):
            projects = {}

        return {
            "version": raw.get("version", 1),
            "projects": projects,
        }

    def get_policy(
        self,
        *,
        user_id: str,
        project_id: str,
    ) -> ProjectPrivacyPolicy:
        user_id = str(user_id or "anonymous")
        project_id = str(project_id or "default")

        data = self._read()
        record = data["projects"].get(project_id)

        if not isinstance(record, dict):
            return ProjectPrivacyPolicy(
                user_id=user_id,
                project_id=project_id,
                mode=ProjectPrivacyMode.PRIVATE,
            )

        raw_mode = str(
            record.get("privacy_mode", "private")
        ).strip().lower()

        try:
            mode = ProjectPrivacyMode(raw_mode)
        except ValueError:
            mode = ProjectPrivacyMode.PRIVATE

        return ProjectPrivacyPolicy(
            user_id=user_id,
            project_id=project_id,
            mode=mode,
        )

    def set_policy(
        self,
        *,
        project_id: str,
        privacy_mode: ProjectPrivacyMode | str,
    ) -> ProjectPrivacyPolicy:
        project_id = str(project_id or "").strip()

        if not project_id:
            raise ValueError("project_id is required")

        try:
            mode = ProjectPrivacyMode(
                str(
                    getattr(
                        privacy_mode,
                        "value",
                        privacy_mode,
                    )
                ).strip().lower()
            )
        except ValueError:
            raise ValueError(
                f"invalid privacy mode: {privacy_mode}"
            )

        data = self._read()

        data["projects"][project_id] = {
            "privacy_mode": mode.value,
        }

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=str(self.path.parent),
            text=True,
        )

        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(
                    data,
                    handle,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temp_name,
                self.path,
            )
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

        return ProjectPrivacyPolicy(
            user_id="system",
            project_id=project_id,
            mode=mode,
        )


def authoritative_project_policy(
    *,
    user_id: str,
    project_id: str,
    registry: Optional[ProjectPolicyRegistry] = None,
) -> ProjectPrivacyPolicy:
    registry = registry or ProjectPolicyRegistry()

    return registry.get_policy(
        user_id=user_id,
        project_id=project_id,
    )
