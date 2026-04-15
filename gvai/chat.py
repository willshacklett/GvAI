from typing import Any, Dict, List, Optional
from gvai.core import GvCore
from gvai.llm import generate_llm_response


class GvChat:
    def __init__(self):
        self.core = GvCore()
        self.turn_index = 0
        self.conversation_gv = 1.0
        self.last_result: Optional[Dict[str, Any]] = None
        self.last_gv_state: Optional[Dict[str, Any]] = None

    def reset(self) -> Dict[str, Any]:
        self.turn_index = 0
        self.conversation_gv = 1.0
        self.last_result = None
        self.last_gv_state = {
            "gv": 1.0,
            "intent": "unknown",
            "topic": "general",
            "constraints": [],
            "tone": "clean",
            "trajectory": "starting",
            "memory_anchor": "fresh_session",
            "decision_trace": [],
        }
        return {
            "ok": True,
            "conversation": {
                "canonical_gv": 1.0,
                "conversation_gv": 1.0,
                "state": "STABLE",
                "turn_index": 0,
            },
            "gv_state": self.last_gv_state,
        }

    def _fallback_reply(self, user_text: str) -> str:
        return f"GvAI received: {user_text}"

    def _derive_conversation(self, gv_result: Dict[str, Any]) -> Dict[str, Any]:
        metrics = gv_result.get("metrics", {})
        score = float(metrics.get("gv_score", 1.0))
        self.turn_index += 1
        self.conversation_gv = score

        if score >= 0.85:
            state = "STABLE"
        elif score >= 0.70:
            state = "DEGRADED"
        else:
            state = "CRITICAL"

        return {
            "canonical_gv": 1.0,
            "conversation_gv": round(self.conversation_gv, 3),
            "state": state,
            "turn_index": self.turn_index,
        }

    def _infer_intent(self, user_text: str) -> str:
        t = user_text.lower()
        if "who" in t or "what" in t or "when" in t or "where" in t:
            return "informational_query"
        if "build" in t or "code" in t or "script" in t:
            return "build_request"
        if "explain" in t or "why" in t or "how" in t:
            return "explanation"
        return "general"

    def _infer_topic(self, user_text: str, prior_state: Optional[Dict[str, Any]]) -> str:
        t = user_text.lower()
        if "king" in t or "england" in t or "uk" in t or "charles" in t:
            return "british_monarchy"
        if "gv" in t or "god variable" in t:
            return "god_variable"
        if "app" in t or "api" in t or "backend" in t or "frontend" in t:
            return "software_system"
        if prior_state and prior_state.get("topic"):
            return str(prior_state["topic"])
        return "general"

    def _infer_constraints(self, user_text: str) -> List[str]:
        t = user_text.lower()
        constraints: List[str] = []
        if any(word in t for word in ["who", "what", "when", "where", "fact", "current"]):
            constraints.append("factual")
        if any(word in t for word in ["history", "king", "war", "timeline"]):
            constraints.append("historical")
        if any(word in t for word in ["code", "build", "script", "api"]):
            constraints.append("technical")
        return constraints

    def _infer_tone(self, user_text: str, prior_state: Optional[Dict[str, Any]]) -> str:
        if prior_state and prior_state.get("tone"):
            return str(prior_state["tone"])
        t = user_text.lower()
        if "simple" in t:
            return "simple"
        if "short" in t:
            return "short"
        if "dramatic" in t:
            return "dramatic"
        return "clean"

    def _infer_trajectory(self, user_text: str, prior_state: Optional[Dict[str, Any]]) -> str:
        t = user_text.lower()
        if any(word in t for word in ["more", "deeper", "expand", "details"]):
            return "deepening"
        if any(word in t for word in ["build", "make", "implement"]):
            return "building"
        if any(word in t for word in ["fix", "debug", "repair"]):
            return "repairing"
        if any(word in t for word in ["who", "what", "when", "where", "why", "how"]):
            return "clarifying"
        if prior_state and prior_state.get("trajectory"):
            return str(prior_state["trajectory"])
        return "continuing"

    def _build_gv_state(
        self,
        user_text: str,
        reply: str,
        conversation: Dict[str, Any],
        decision: Optional[str],
        prior_state: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        intent = self._infer_intent(user_text)
        topic = self._infer_topic(user_text, prior_state)
        constraints = self._infer_constraints(user_text)
        tone = self._infer_tone(user_text, prior_state)
        trajectory = self._infer_trajectory(user_text, prior_state)

        decision_trace: List[str] = []
        if prior_state and isinstance(prior_state.get("decision_trace"), list):
            decision_trace = [str(x) for x in prior_state["decision_trace"][-4:]]

        anchor = f"{topic}:{intent}"
        decision_trace.append(f"user:{user_text[:80]}")
        if decision:
            decision_trace.append(f"decision:{decision}")
        decision_trace.append(f"anchor:{anchor}")

        return {
            "gv": conversation.get("conversation_gv", 1.0),
            "intent": intent,
            "topic": topic,
            "constraints": constraints,
            "tone": tone,
            "trajectory": trajectory,
            "memory_anchor": anchor,
            "decision_trace": decision_trace[-6:],
        }

    def chat(self, user_text: str, gv_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        system_state = gv_state or self.last_gv_state

        llm_prompt = f"""
You are GvAI, a continuity-aware AI.
Use the provided GV state as compressed conversational continuity.

GV State:
{system_state}

Rules:
- Preserve intent, topic, tone, and trajectory.
- Do not claim hidden memory beyond this GV state.
- If the state is ambiguous, answer carefully and clarify.
- Keep responses useful and direct.
"""
        composed_user = f"{llm_prompt}\n\nUser message:\n{user_text}"

        reply = generate_llm_response(
            user_message=composed_user,
            history=None,
            mode="simple",
        ) or self._fallback_reply(user_text)

        joined_text = f"USER: {user_text}\nASSISTANT: {reply}"
        gv_result = self.core.evaluate(joined_text)
        conversation = self._derive_conversation(gv_result)

        updated_gv_state = self._build_gv_state(
            user_text=user_text,
            reply=reply,
            conversation=conversation,
            decision=gv_result.get("decision"),
            prior_state=system_state,
        )
        self.last_gv_state = updated_gv_state

        result = {
            "ok": True,
            "input": user_text,
            "reply": reply,
            "decision": gv_result.get("decision"),
            "metrics": gv_result.get("metrics", {}),
            "conversation": conversation,
            "gv_state": updated_gv_state,
            "timestamp": gv_result.get("timestamp"),
        }
        self.last_result = result
        return result

    def get_state(self) -> Dict[str, Any]:
        if self.last_result is None:
            return self.reset()
        return {
            "ok": True,
            "conversation": self.last_result.get("conversation", {}),
            "last_decision": self.last_result.get("decision"),
            "last_metrics": self.last_result.get("metrics", {}),
            "gv_state": self.last_result.get("gv_state", self.last_gv_state),
        }
