from __future__ import annotations

from typing import Any, Dict


def estimate_recovery_half_life(timeline: Dict[str, Any]) -> Dict[str, Any]:
    events = timeline.get("events", []) or []

    if len(events) < 3:
        return {
            "status": "INSUFFICIENT_DATA",
            "half_life_events": None,
            "reason": "Need at least 3 phase events."
        }

    peak_debt = max(float(e.get("debt", 0.0) or 0.0) for e in events)

    if peak_debt <= 0:
        return {
            "status": "NO_DEBT_OBSERVED",
            "half_life_events": 0,
            "reason": "No recovery debt observed."
        }

    half_debt = peak_debt / 2.0
    peak_index = next(
        i for i, e in enumerate(events)
        if float(e.get("debt", 0.0) or 0.0) == peak_debt
    )

    recovery_index = None

    for i, event in enumerate(events[peak_index:], start=peak_index):
        debt = float(event.get("debt", 0.0) or 0.0)

        if debt <= half_debt:
            recovery_index = i
            break

    if recovery_index is None:
        return {
            "status": "NOT_RECOVERED_HALF_DEBT",
            "peak_debt": peak_debt,
            "half_debt": round(half_debt, 3),
            "half_life_events": None,
            "reason": "Debt has not recovered to half of peak."
        }

    half_life = recovery_index - peak_index

    return {
        "status": "RECOVERED_HALF_DEBT",
        "peak_debt": peak_debt,
        "half_debt": round(half_debt, 3),
        "half_life_events": half_life,
        "reason": "Debt recovered to half of peak."
    }
