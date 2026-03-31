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

    return {
        "gv_score": round(latest["gv_score"], 3),
        "avg_gv": round(sum(scores) / len(scores), 3),
        "delta_gv": round(delta_gv, 3),
        "trend": trend,
        "volatility": round(avg_abs_diff, 3),
        "recoverability": latest["recoverability"],
        "risk": latest["risk"],
        "timestamp": latest["timestamp"],
        "label": latest["label"],
    }


def decision_from_summary(summary: Dict[str, object]) -> str:
    gv = summary["gv_score"]
    trend = summary["trend"]
    volatility = summary["volatility"]

    if gv is None:
        return "NO_DATA"

    if gv < 0.55:
        return "REFUSE"

    if trend == "DEGRADING" and volatility is not None and volatility >= 0.12:
        if gv < 0.68:
            return "SIMULATE"
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

    header = f"Latest system snapshot: label={label}, timestamp={timestamp}, gv={gv}, trend={trend}, volatility={volatility}."

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
