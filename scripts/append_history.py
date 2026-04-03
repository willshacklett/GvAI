import json
import os
from datetime import datetime, timezone
from pathlib import Path

HISTORY_PATH = Path("public_site/history.json")
LATEST_PATH = Path("public_site/latest.json")

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

history = load_json(HISTORY_PATH, [])
if not isinstance(history, list):
    history = []

latest = load_json(LATEST_PATH, {})
if not isinstance(latest, dict):
    latest = {}

last_seq = 0
if history and isinstance(history[-1], dict):
    last_seq = int(history[-1].get("seq", 0) or 0)

def pick(name, default=None):
    env_val = os.getenv(name)
    if env_val not in (None, ""):
        return env_val
    return latest.get(name.lower(), default)

def to_int(val, default=0):
    try:
        return int(float(val))
    except Exception:
        return default

entry = {
    "seq": last_seq + 1,
    "godscore": to_int(pick("GODSCORE", latest.get("godscore", 0)), 0),
    "status": str(pick("STATUS", latest.get("status", "unknown"))),
    "mean_step": to_int(pick("MEAN_STEP", latest.get("mean_step", 0)), 0),
    "collapse_step": to_int(pick("COLLAPSE_STEP", latest.get("collapse_step", 0)), 0),
    "lead_time": to_int(pick("LEAD_TIME", latest.get("lead_time", 0)), 0),
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "sha": os.getenv("GITHUB_SHA", "")[:7],
    "source": "github-actions"
}

history.append(entry)

HISTORY_PATH.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")

print(f"Appended seq={entry['seq']}")
print(json.dumps(entry, indent=2))
