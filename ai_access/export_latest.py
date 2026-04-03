import json
from pathlib import Path

public_dir = Path("public_site")
public_dir.mkdir(parents=True, exist_ok=True)

src = Path("ci/action_result.json")
dst = public_dir / "latest.json"

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

data = fallback
if src.exists():
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        data = fallback

dst.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("Saved public_site/latest.json")
