import json
from pathlib import Path

src = Path("ci/action_result.json")

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
    "reasons": ["fallback"]
}

data = fallback
if src.exists():
    try:
        data = json.loads(src.read_text())
    except:
        pass

Path("public/latest_result.json").write_text(
    json.dumps(data, indent=2)
)

print("Saved public/latest_result.json")
