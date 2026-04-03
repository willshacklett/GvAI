import json
from pathlib import Path

public_dir = Path("public_site")
public_dir.mkdir(parents=True, exist_ok=True)

latest_path = public_dir / "latest.json"
history_path = public_dir / "history.json"

fallback = {
    "godscore": 5,
    "status": "collapse",
    "passed": False,
    "fired": True,
    "mean_step": 20,
    "drift_step": 4,
    "breach_step": None,
    "collapse_step": 31,
    "lead_time": 11,
    "reasons": [
        "mean slope trigger detected",
        "drift confirmed",
        "gated sentinel fired",
        "collapse threshold crossed"
    ]
}

latest = fallback
if latest_path.exists():
    try:
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        latest = fallback

history = []
if history_path.exists():
    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

entry = {
    "seq": len(history) + 1,
    "godscore": latest.get("godscore"),
    "status": latest.get("status"),
    "passed": latest.get("passed"),
    "fired": latest.get("fired"),
    "mean_step": latest.get("mean_step"),
    "drift_step": latest.get("drift_step"),
    "breach_step": latest.get("breach_step"),
    "collapse_step": latest.get("collapse_step"),
    "lead_time": latest.get("lead_time"),
    "reasons": latest.get("reasons", [])
}

history.append(entry)

# keep last 50 only
history = history[-50:]

history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")

print("Saved public_site/history.json")
print(f"History length: {len(history)}")
