"""
Explicit configured-model execution verification for GVAI Private Build Mode.

This command intentionally executes the operator-configured private model through
the normal protected runtime. It emits only a sanitized verification report:
never the model reply, configured command, paths, environment values, secrets,
or raw exception text.

This verification is evidence for one configured execution attempt. It does not
establish production readiness.
"""

from __future__ import annotations

import json
from typing import Any

from privacy import runtime


_SYSTEM_PROMPT = (
    "You are executing a GVAI private-runtime verification request. "
    "Return a short response."
)

_USER_CONTENT = (
    "Synthetic verification input. No sensitive data is present."
)


def verify_configured_model_execution(
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Execute the configured model once through the protected private runtime."""

    report: dict[str, Any] = {
        "scope": "configured_model_execution",
        "configured_model_execution": "fail",
        "production_ready": False,
    }

    try:
        if not runtime.private_build_enabled():
            return report

        if not runtime.encrypted_workspace_enabled():
            return report

        result = runtime.run_private_model(
            _SYSTEM_PROMPT,
            _USER_CONTENT,
            timeout=timeout,
        )

        if result.get("provider") != "local":
            return report

        if result.get("network_isolated") is not True:
            return report

        reply = result.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            return report

    except Exception:
        return report

    report["configured_model_execution"] = "pass"
    return report


def main() -> int:
    report = verify_configured_model_execution()

    print(
        json.dumps(
            report,
            sort_keys=True,
            separators=(",", ":"),
        )
    )

    return 0 if report["configured_model_execution"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
