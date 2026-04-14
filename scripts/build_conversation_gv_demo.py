import json
import os
import time
from gvai.core import GvCore

core = GvCore()

sample_turns = [
    "This system is stable, recoverable, coherent, and measured.",
    "We can stay controlled, bounded, and resilient while preserving continuity.",
    "There is drift risk and uncertainty in the current output.",
    "Everything must change immediately and this could become critical and irreversible.",
    "We recover by returning to a stable, controlled, recoverable state.",
]

results = []
for text in sample_turns:
    results.append(core.evaluate(text))

latest = results[-1]["conversation"]

payload = {
    "generated_at": time.time(),
    "summary": {
        "canonical_gv": latest["canonical_gv"],
        "conversation_gv": latest["conversation_gv"],
        "state": latest["state"],
        "turn_index": latest["turn_index"],
    },
    "turns": [
        {
            "input": r["input"],
            "decision": r["decision"],
            "gv_score": r["metrics"]["gv_score"],
            "drift_risk": r["metrics"]["drift_risk"],
            "irreversibility_risk": r["metrics"]["irreversibility_risk"],
            "conversation_gv": r["conversation"]["conversation_gv"],
            "conversation_state": r["conversation"]["state"],
            "turn_index": r["conversation"]["turn_index"],
        }
        for r in results
    ],
}

os.makedirs("dashboard", exist_ok=True)
with open("dashboard/conversation_gv_demo.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)

print("Wrote dashboard/conversation_gv_demo.json")
print(json.dumps(payload["summary"], indent=2))
