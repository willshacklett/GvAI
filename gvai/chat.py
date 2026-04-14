from typing import Any, Dict
from gvai.core import GvCore


class GvChat:
    def __init__(self):
        self.core = GvCore()
        self._turn_index = 0
        self._conversation_gv = 1.0

    def reset(self) -> Dict[str, Any]:
        if hasattr(self.core, "reset_conversation"):
            self.core.reset_conversation()
        self._turn_index = 0
        self._conversation_gv = 1.0
        return {
            "ok": True,
            "conversation": {
                "canonical_gv": 1.0,
                "conversation_gv": 1.0,
                "state": "STABLE",
                "turn_index": 0,
            },
        }

    def _fallback_reply(self, user_text: str) -> str:
        return f"GvAI received: {user_text}"

    def _derive_conversation(self, gv_result: Dict[str, Any]) -> Dict[str, Any]:
        if "conversation" in gv_result:
            return gv_result["conversation"]

        metrics = gv_result.get("metrics", {})
        score = float(metrics.get("gv_score", 1.0))
        self._turn_index += 1
        self._conversation_gv = score

        if score >= 0.85:
            state = "STABLE"
        elif score >= 0.70:
            state = "DEGRADED"
        else:
            state = "CRITICAL"

        return {
            "canonical_gv": 1.0,
            "conversation_gv": round(self._conversation_gv, 3),
            "state": state,
            "turn_index": self._turn_index,
        }

    def chat(self, user_text: str) -> Dict[str, Any]:
        reply = self._fallback_reply(user_text)
        joined_text = f"USER: {user_text}\nASSISTANT: {reply}"
        gv_result = self.core.evaluate(joined_text)
        conversation = self._derive_conversation(gv_result)

        return {
            "ok": True,
            "input": user_text,
            "reply": reply,
            "decision": gv_result.get("decision"),
            "metrics": gv_result.get("metrics", {}),
            "conversation": conversation,
            "timestamp": gv_result.get("timestamp"),
        }
