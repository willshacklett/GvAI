from typing import Iterable, Dict, Any, List
import numpy as np

from .sentinel import RecoverabilitySentinel, SentinelState


def run_sentinel_series(
    series: Iterable[Iterable[float]],
    *,
    var_threshold: float = 0.018,
    drift_threshold: float = 0.0015,
    persist_steps: int = 4,
    collapse_mean: float = 1.55,
    rolling_window: int = 6,
) -> Dict[str, Any]:
    sentinel = RecoverabilitySentinel(
        var_threshold=var_threshold,
        drift_threshold=drift_threshold,
        persist_steps=persist_steps,
        collapse_mean=collapse_mean,
        rolling_window=rolling_window,
    )

    timeline: List[Dict[str, Any]] = []
    final_state: SentinelState | None = None

    for x in series:
        state = sentinel.update(np.asarray(x, dtype=float))
        info = sentinel.explain(state)
        timeline.append(info)
        final_state = state

    if final_state is None:
        return {
            "status": "empty",
            "fired": False,
            "breach_step": None,
            "drift_step": None,
            "collapse_step": None,
            "lead_time": None,
            "reasons": ["no data"],
            "timeline": [],
        }

    final_info = sentinel.explain(final_state)

    return {
        "status": final_info["status"],
        "fired": final_info["fired"],
        "breach_step": final_info["breach_step"],
        "drift_step": final_info["drift_step"],
        "collapse_step": final_info["collapse_step"],
        "lead_time": final_info["lead_time"],
        "reasons": final_info["reasons"],
        "timeline": timeline,
    }


def summarize_timeline(result: Dict[str, Any]) -> Dict[str, Any]:
    timeline = result.get("timeline", [])
    if not timeline:
        return {
            "status": "empty",
            "first_warning": None,
            "first_critical": None,
            "first_collapse": None,
            "lead_time": None,
        }

    first_warning = None
    first_critical = None
    first_collapse = None

    for row in timeline:
        status = row.get("status")
        t = row.get("t")
        if status == "warning" and first_warning is None:
            first_warning = t
        if status == "critical" and first_critical is None:
            first_critical = t
        if status == "collapse" and first_collapse is None:
            first_collapse = t

    return {
        "status": result.get("status"),
        "first_warning": first_warning,
        "first_critical": first_critical,
        "first_collapse": first_collapse,
        "lead_time": result.get("lead_time"),
    }
