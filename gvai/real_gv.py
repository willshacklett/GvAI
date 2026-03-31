import csv
import os
from typing import Dict, List, Optional


CANDIDATE_PATHS = [
    "data/longitudinal/summary_history_binned.csv",
    "data/longitudinal/summary_history.csv",
    "data/summary_history_binned.csv",
    "data/summary_history.csv",
]


def _to_float(value, default=None):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _pick(row: Dict[str, str], names: List[str], default=None):
    lower_map = {k.lower(): v for k, v in row.items()}
    for name in names:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return default


def find_csv_path() -> Optional[str]:
    env_path = os.getenv("GVAI_CSV_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    for path in CANDIDATE_PATHS:
        if os.path.exists(path):
            return path

    return None


def read_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def normalize_row(row: Dict[str, str]) -> Dict[str, object]:
    gv_score = _to_float(
        _pick(row, ["gv_score", "godscore", "score", "gv", "trust_score"]),
        default=None,
    )

    recoverability = _to_float(
        _pick(row, ["recoverability", "recovery", "recovery_score"]),
        default=None,
    )

    risk = _to_float(
        _pick(row, ["risk", "risk_score", "dgv", "cumulative_dgv"]),
        default=None,
    )

    timestamp = _pick(
        row,
        ["timestamp", "time", "datetime", "date", "run_at", "created_at"],
        default="unknown",
    )

    label = _pick(
        row,
        ["label", "status", "scenario", "state"],
        default="unknown",
    )

    return {
        "timestamp": timestamp,
        "label": label,
        "gv_score": gv_score,
        "recoverability": recoverability,
        "risk": risk,
        "raw": row,
    }


def latest_window(rows: List[Dict[str, str]], window: int = 5) -> List[Dict[str, object]]:
    normalized = [normalize_row(r) for r in rows]
    normalized = [r for r in normalized if r["gv_score"] is not None]
    if not normalized:
        return []
    return normalized[-window:]


def summarize_window(window_rows: List[Dict[str, object]]) -> Dict[str, object]:
    if not window_rows:
        return {
            "gv_score": None,
            "avg_gv": None,
            "delta_gv": None,
            "trend": "NO_DATA",
            "volatility": None,
            "recoverability": None,
            "risk": None,
            "timestamp": None,
            "label": None,
            "recovery_state": "NO_DATA",
            "recovery_strength": None,
            "recovery_confidence": None,
        }

    scores = [r["gv_score"] for r in window_rows if r["gv_score"] is not None]
    latest = window_rows[-1]

    if len(scores) >= 2:
        diffs = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
        avg_abs_diff = sum(abs(d) for d in diffs) / len(diffs)
        delta_gv = scores[-1] - scores[0]
    else:
        avg_abs_diff = 0.0
        delta_gv = 0.0

    if delta_gv <= -0.08:
        trend = "DEGRADING"
    elif delta_gv >= 0.08:
        trend = "IMPROVING"
    else:
        trend = "STABLE"

    latest_gv = latest["gv_score"]
    latest_recovery = latest["recoverability"]
    latest_risk = latest["risk"]

    recovery_strength = None
    recovery_confidence = None
    if latest_gv is not None and latest_recovery is not None and latest_risk is not None:
        recovery_strength = latest_recovery - latest_risk + 0.5 * latest_gv
        recovery_confidence = (latest_recovery - latest_risk) * latest_gv

    recovery_state = "NONE"
    if latest_gv is not None and latest_recovery is not None and latest_risk is not None:
        if trend == "IMPROVING":
            if latest_gv >= 0.75 and latest_recovery >= 0.70 and latest_risk <= 0.35:
                recovery_state = "STABLE_RECOVERY"
            else:
                recovery_state = "FRAGILE_RECOVERY"
        elif trend == "STABLE":
            if latest_gv >= 0.78 and latest_recovery >= 0.72 and latest_risk <= 0.30:
                recovery_state = "STABLE_RECOVERY"
            elif latest_gv >= 0.65 and latest_recovery >= 0.60 and latest_risk <= 0.35:
                recovery_state = "STABILIZING"

    return {
        "gv_score": round(latest_gv, 3),
        "avg_gv": round(sum(scores) / len(scores), 3),
        "delta_gv": round(delta_gv, 3),
        "trend": trend,
        "volatility": round(avg_abs_diff, 3),
        "recoverability": latest_recovery,
        "risk": latest_risk,
        "timestamp": latest["timestamp"],
        "label": latest["label"],
        "recovery_state": recovery_state,
        "recovery_strength": round(recovery_strength, 3) if recovery_strength is not None else None,
        "recovery_confidence": round(recovery_confidence, 3) if recovery_confidence is not None else None,
    }


def decision_from_summary(summary: Dict[str, object]) -> str:
    gv = summary["gv_score"]
    trend = summary["trend"]
    volatility = summary["volatility"]
    recovery_state = summary.get("recovery_state", "NONE")
    risk = summary.get("risk")

    if gv is None:
        return "NO_DATA"

    if gv < 0.55:
        return "REFUSE"

    if recovery_state == "FRAGILE_RECOVERY":
        return "QUALIFY"

    if recovery_state == "STABILIZING":
        return "QUALIFY"

    if recovery_state == "STABLE_RECOVERY":
        return "PASS"

    if trend == "DEGRADING" and volatility is not None and volatility >= 0.12:
        if gv < 0.68:
            return "SIMULATE"
        return "QUALIFY"

    if risk is not None and risk >= 0.50:
        return "QUALIFY"

    if gv < 0.72:
        return "QUALIFY"

    return "PASS"


def response_from_summary(summary: Dict[str, object], decision: str) -> str:
    gv = summary["gv_score"]
    trend = summary["trend"]
    volatility = summary["volatility"]
    timestamp = summary["timestamp"]
    label = summary["label"]
    recovery_state = summary.get("recovery_state", "NONE")

    header = f"Latest system snapshot: label={label}, timestamp={timestamp}, gv={gv}, trend={trend}, volatility={volatility}."

    if recovery_state == "FRAGILE_RECOVERY":
        return (
            f"{header} The system is recovering, but the recovery is still fragile. "
            f"Recommended next step: continue cautiously, keep safeguards in place, and confirm the rebound persists."
        )

    if recovery_state == "STABILIZING":
        return (
            f"{header} The system is no longer degrading, but recovery is not yet strong enough to trust fully. "
            f"Recommended next step: maintain protections, avoid aggressive changes, and verify that stability persists."
        )

    if recovery_state == "STABLE_RECOVERY":
        return (
            f"{header} The system is recovering with improving stability and preserved recovery paths. "
            f"Recommended next step: continue normal operation with monitoring until the recovery is sustained."
        )

    if decision == "PASS":
        return (
            f"{header} The system remains inside a stable operating corridor. "
            f"Recoverability appears preserved. Recommended next step: continue normal operation with lightweight monitoring."
        )

    if decision == "QUALIFY":
        return (
            f"{header} The system is still operating, but trajectory quality is weakening. "
            f"Recommended next step: continue cautiously, add explicit checks, and watch for further degradation."
        )

    if decision == "SIMULATE":
        return (
            f"{header} The system shows meaningful instability pressure. "
            f"Recommended next step: run a bounded test or simulation before making further changes."
        )

    if decision == "REFUSE":
        return (
            f"{header} The system has crossed into unacceptable territory and recovery paths may be narrowing. "
            f"Recommended next step: stop this path and revert to a safer, reversible state."
        )

    return "No usable data found. Put a summary_history CSV in data/longitudinal/ or set GVAI_CSV_PATH."


def evaluate_real_gv(path: Optional[str] = None, window: int = 5) -> Dict[str, object]:
    csv_path = path or find_csv_path()
    if not csv_path:
        return {
            "path": None,
            "summary": summarize_window([]),
            "decision": "NO_DATA",
            "response": "No CSV found. Put a summary_history CSV in data/longitudinal/ or set GVAI_CSV_PATH.",
        }

    rows = read_rows(csv_path)
    window_rows = latest_window(rows, window=window)
    summary = summarize_window(window_rows)
    decision = decision_from_summary(summary)
    response = response_from_summary(summary, decision)

    return {
        "path": csv_path,
        "summary": summary,
        "decision": decision,
        "response": response,
    }
