from __future__ import annotations

from typing import Any

__all__ = [
    "RecoverabilitySentinel",
    "SentinelState",
    "run_sentinel_series",
    "summarize_timeline",
]


def __getattr__(name: str) -> Any:
    if name in {"RecoverabilitySentinel", "SentinelState"}:
        from .sentinel import RecoverabilitySentinel, SentinelState

        return {
            "RecoverabilitySentinel": RecoverabilitySentinel,
            "SentinelState": SentinelState,
        }[name]

    if name in {"run_sentinel_series", "summarize_timeline"}:
        from .api import run_sentinel_series, summarize_timeline

        return {
            "run_sentinel_series": run_sentinel_series,
            "summarize_timeline": summarize_timeline,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
