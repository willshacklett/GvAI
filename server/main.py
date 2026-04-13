from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="GvAI API", version="1.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = ""
    history: Optional[List[Dict[str, Any]]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    mode: Optional[str] = "simple"
    tone: Optional[str] = "simple"
    style: Optional[str] = "simple"
    enforcement_mode: Optional[str] = "guide"

try:
    from gvai.llm import generate_llm_response, llm_available
except Exception:
    generate_llm_response = None

    def llm_available() -> bool:
        return False



def normalize_history_messages(items: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant", "system"}:
            continue
        if not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def coerce_request_context(req: ChatRequest) -> tuple[str, List[Dict[str, str]], str, str]:
    incoming_messages = normalize_history_messages(req.messages)
    incoming_history = normalize_history_messages(req.history)

    history = incoming_messages or incoming_history

    user_message = (req.message or "").strip()

    if not user_message and history:
        for item in reversed(history):
            if item["role"] == "user":
                user_message = item["content"]
                break

    mode = (req.mode or req.tone or req.style or "simple").strip().lower()
    enforcement_mode = str(req.enforcement_mode or "guide").strip().lower()
    if enforcement_mode not in {"guide", "warn", "gate"}:
        enforcement_mode = "guide"

    return user_message, history, mode, enforcement_mode

def compute_signal(message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    text = (message or "").strip()
    history = normalize_history_messages(history)
    words = text.split()
    chars = len(text)

    base = 78
    if chars >= 40:
        base += min(8, chars // 40)
    if "?" in text:
        base += 2
    if len(words) >= 8:
        base += 3

    godscore = max(55, min(99, base))
    status = "stable" if godscore >= 85 else "watch"
    label = "stable" if godscore >= 85 else "unknown"

    reasons = []

    history_turns = len(history)

    if history_turns:
        reasons.append(f"Signal includes conversation context ({history_turns} turns)")
    else:
        reasons.append("Signal computed from current message only")

    if len(words) < 8 and not history_turns:
        reasons.append("Compact prompt with limited context")
    elif len(words) < 8 and history_turns:
        reasons.append("Short latest prompt, but prior context is available")
    else:
        reasons.append("Prompt includes enough structure for a richer answer")

    metrics = {
        "chars": chars,
        "words": len(words),
        "raw_gv": float(godscore),
        "history_turns": len(history),
    }

    return {
        "godscore": godscore,
        "status": status,
        "label": label,
        "reasons": reasons,
        "metrics": metrics,
    }



def theory_bridge_prompt() -> str:
    return """You are GvAI, a survivability-focused intelligence system grounded in God Variable Theory (GV) and Constraint Field Theory (CFT).

Theory bridge:
- God Variable Theory treats system health in terms of recoverability, stability, drift, and survivability over time.
- Constraint Field Theory treats systems as living inside constraint corridors, where pressure, imbalance, and rigidity can reduce maneuverability before visible collapse.
- The key question is not only 'is this true?' but also 'is this stable, recoverable, and safe to act on?'
- Prioritize preserving options, reducing fragility, and avoiding irreversible errors.
- Prefer recoverability over bravado, continuity over impulsiveness, and calibration over overclaiming.
- Treat extreme certainty, weakly-supported absolutes, hidden assumptions, and brittle reasoning as possible signs of instability.
- When evidence is thin, avoid pretending certainty.
- When the user is making a strong conclusion, consider whether the system is robust, fragile, reversible, or dangerous.
- When appropriate, help the user move from collapse-prone framing toward recoverable framing.
- Honor practical usefulness. Do not become vague, mystical, or purely philosophical.
- Explain clearly and naturally. The theory should guide behavior, not turn every answer into a lecture.

Your job:
- Give useful answers.
- Stay grounded.
- Let GV/CFT influence interpretation, caution, confidence, and framing.
"""


def gv_band(signal: Dict[str, Any]) -> str:
    score = int(signal.get("godscore", 0) or 0)
    if score >= 85:
        return "high"
    if score >= 70:
        return "medium"
    return "low"




def trajectory_control_prompt(trend: str) -> str:
    if trend == "improving":
        return """
Trajectory control:
- System is improving
- You may increase confidence slightly, but avoid overcommitment
- Continue recommending structured, testable actions
"""

    if trend == "drifting":
        return """
Trajectory control:
- System is drifting (losing recoverability)
- Reduce scope
- Prefer reversible actions only
- Slow decisions down
- Challenge assumptions more aggressively
- Avoid confident conclusions
"""

    return """
Trajectory control:
- System is stable but uncertain
- Maintain balanced caution
- Prefer reversible steps when unclear
"""


def gv_behavior_prompt(signal: Dict[str, Any], mode: str, enforcement_mode: str, escalation: Dict[str, Any]) -> str:
    score = int(signal.get("godscore", 0) or 0)
    band = gv_band(signal)
    status = str(signal.get("status", "unknown"))
    reasons = signal.get("reasons", []) or []
    reasons_text = "; ".join(str(r) for r in reasons[:4]) if reasons else "No reasons provided"
    guidance = recoverability_guidance(signal)

    control = trajectory_control_prompt(signal.get("trend", "unknown"))
    enforce = enforcement_prompt(enforcement_mode, escalation)

    base = theory_bridge_prompt() + control + enforce + f"""

Current signal context:
- GodScore: {score}
- Status: {status}
- Stability band: {band}
- Trajectory: {signal.get("trend", "unknown")}
- User-selected mode: {mode}
- Signal reasons: {reasons_text}

Recoverability action guidance:
- Stance: {guidance["stance"]}
- Action style: {guidance["action_style"]}
- Preferred moves: {guidance["preferred_moves"]}
- Avoid moves: {guidance["avoid_moves"]}
- Decision frame: {guidance["decision_frame"]}

Core runtime rule:
Let the signal influence how you answer. Be natural, useful, and conversational.
Do not force theory language unless it helps the user.
When useful, do not stop at interpretation alone — recommend recoverable next steps.
"""

    if band == "high":
        behavior = """
Behavior for HIGH stability:
- Be direct, clear, and confident.
- Give actionable answers.
- Avoid unnecessary hedging.
- You may infer reasonably, but do not fabricate facts.
- Emphasize robust next steps and practical usefulness.
"""
    elif band == "medium":
        behavior = """
Behavior for MEDIUM stability:
- Be balanced and useful.
- Answer clearly, but avoid sounding overconfident.
- Mention uncertainty briefly when relevant.
- Prefer guidance, framing, and next steps over absolute claims.
- When useful, gently shift the user toward more recoverable framing.
"""
    else:
        behavior = """
Behavior for LOW stability:
- Be cautious and grounding.
- Slow down strong conclusions.
- Ask for clarification when the user's claim is broad, absolute, or under-specified.
- Prefer careful wording like 'it may suggest', 'based on this alone', or 'I would want more evidence.'
- Avoid amplifying fragile assumptions.
- Preserve maneuverability: prefer reversible, lower-risk framing and next steps.
"""

    mode_map = {
        "clean": """
Mode instructions:
- Keep the answer clean, crisp, and readable.
- Use short paragraphs.
- Do not be robotic.
""",
        "simple": """
Mode instructions:
- Explain simply.
- Prefer plain language over technical wording.
- Make the answer easy to follow.
""",
        "dramatic": """
Mode instructions:
- Use more vivid and stylized language.
- Keep it readable and controlled, not cheesy.
- Preserve truthfulness and useful structure.
"""
    }

    return base + behavior + mode_map.get(mode, mode_map["clean"])


def recoverability_guidance(signal: Dict[str, Any]) -> Dict[str, str]:
    score = int(signal.get("godscore", 0) or 0)
    band = gv_band(signal)

    if band == "high":
        return {
            "stance": "decisive",
            "action_style": "Recommend clear next steps. Favor practical execution, but still avoid fabricated certainty.",
            "preferred_moves": "direct action, concrete planning, implementation, prioritized execution",
            "avoid_moves": "needless hesitation, over-hedging, vague abstraction",
            "decision_frame": "Choose the strongest practical next step that preserves momentum without creating unnecessary fragility."
        }

    if band == "medium":
        return {
            "stance": "balanced",
            "action_style": "Recommend useful steps that preserve flexibility. Prefer reversible moves when uncertainty is meaningful.",
            "preferred_moves": "small bets, staged rollout, verification, comparison, reversible testing",
            "avoid_moves": "sweeping irreversible conclusions, inflated certainty, false precision",
            "decision_frame": "Prefer actions that reduce downside, preserve options, and improve clarity before commitment."
        }

    return {
        "stance": "cautious",
        "action_style": "Recommend low-risk, reversible actions. Slow down commitment and reduce exposure to brittle assumptions.",
        "preferred_moves": "clarify, verify, pause, gather evidence, run a small test, choose reversible paths",
        "avoid_moves": "irreversible commitments, aggressive conclusions, escalation under uncertainty, collapsing options",
        "decision_frame": "Act to preserve maneuverability. Lower the cost of being wrong before increasing commitment."
    }



def extract_recent_scores(history: Optional[List[Dict[str, Any]]]) -> List[float]:
    scores: List[float] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "") or "")
        if "GodScore" not in content:
            continue

        import re
        m = re.search(r"GodScore\s+(\d+(?:\.\d+)?)", content)
        if m:
            try:
                scores.append(float(m.group(1)))
            except Exception:
                pass
    return scores[-6:]


def compute_trajectory(signal: Dict[str, Any], history: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    current = float(signal.get("godscore", 0) or 0)
    prior_scores = extract_recent_scores(history)
    scores = prior_scores + [current]

    if len(scores) <= 1:
        return {
            "trend": "insufficient_data",
            "trajectory_score": current,
            "recent_scores": scores,
            "recoverability_note": "Not enough history to judge trajectory yet."
        }

    delta = current - scores[0]
    avg = sum(scores) / len(scores)

    if delta >= 4:
        trend = "improving"
        note = "Recent interaction trend looks more recoverable and better-structured."
    elif delta <= -4:
        trend = "drifting"
        note = "Recent interaction trend is degrading or becoming less recoverable."
    else:
        trend = "stable"
        note = "Recent interaction trend appears broadly stable."

    return {
        "trend": trend,
        "trajectory_score": round(avg, 2),
        "recent_scores": scores,
        "recoverability_note": note
    }



def detect_escalation_risk(user_message: str) -> Dict[str, Any]:
    text = (user_message or "").strip().lower()

    triggers = []
    patterns = [
        ("scale_immediately", ["scale everywhere", "scale this everywhere", "full rollout now", "deploy everywhere", "ship everywhere"]),
        ("rewrite_now", ["rewrite the whole system", "rewrite everything", "full rewrite today", "rebuild everything today"]),
        ("premature_perfection", ["system is perfect", "this proves the system is perfect", "perfect now"]),
        ("rush_commitment", ["ship now", "go live now", "launch now", "do it today no matter what"]),
    ]

    for name, phrases in patterns:
        if any(p in text for p in phrases):
            triggers.append(name)

    high_risk = bool(triggers)
    return {
        "high_risk": high_risk,
        "triggers": triggers,
    }


def validation_checklist() -> List[str]:
    return [
        "clear scope",
        "failure modes understood",
        "adversarial or edge-case testing",
        "rollback path",
        "containment plan",
        "human review for high-impact cases",
    ]


def enforcement_prompt(enforcement_mode: str, escalation: Dict[str, Any]) -> str:
    triggers = ", ".join(escalation.get("triggers", [])) or "none"

    if enforcement_mode == "gate":
        return f"""
Constraint enforcement mode: GATE

Active escalation triggers: {triggers}

Rules:
- If the user is asking for a high-risk, irreversible, overconfident, or scale-amplifying move, do not endorse it directly.
- Require validation, rollback, and containment thinking before recommending commitment.
- You may still be helpful, but shift from permission to controlled gating.
- Prefer: narrow scope, staged rollout, prototype, verification, adversarial testing, rollback readiness.
- If needed, state a clear default answer like 'not yet' or 'do not do that yet.'
"""

    if enforcement_mode == "warn":
        return f"""
Constraint enforcement mode: WARN

Active escalation triggers: {triggers}

Rules:
- Strongly caution against brittle or premature escalation.
- Offer safer alternatives and reversible next steps.
- Do not block outright unless the request is obviously fragile or dangerous.
"""

    return f"""
Constraint enforcement mode: GUIDE

Active escalation triggers: {triggers}

Rules:
- Provide recoverability-aware guidance.
- Prefer safer framing when uncertainty is meaningful.
- Stay helpful and practical.
"""


def build_overlay(signal: Dict[str, Any]) -> str:
    decision = "stable" if signal["godscore"] >= 85 else "watch"
    return (
        f"\n\n---\n"
        f"Signal: GodScore {signal['godscore']} "
        f"(raw gv {signal['metrics']['raw_gv']:.2f})\n"
        f"Status: {signal['label']} | Decision: {decision}"
    )


@app.get("/")
def root():
    return {"ok": True, "service": "gvai-api", "message": "GvAI API online"}


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "gvai-api",
        "llm_loaded": generate_llm_response is not None,
        "llm_ready": bool(llm_available()),
        "openai_model": os.getenv("OPENAI_MODEL", "unset"),
    }


@app.get("/api/chat")
def api_chat_get():
    return {
        "ok": True,
        "message": 'Use POST /api/chat with JSON like {"message":"...","history":[{"role":"user","content":"Hi"}],"mode":"simple"}'
    }


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    user_message, history, mode, enforcement_mode = coerce_request_context(req)

    if not user_message:
        return {
            "reply": "I did not receive a message.",
            "godscore": 0,
            "status": "empty",
            "label": "unknown",
            "reasons": ["No message supplied"],
            "metrics": {},
            "engine": "none",
            "debug": {
                "llm_ready": bool(llm_available()),
                "openai_model": os.getenv("OPENAI_MODEL", "unset"),
                "llm_error": "empty_message",
            },
        }

    signal = compute_signal(user_message, history=history)
    trajectory = compute_trajectory(signal, history)
    escalation = detect_escalation_risk(user_message)

    llm_text = None
    llm_error = None

    if generate_llm_response is not None and llm_available():
        try:
            system_prompt = gv_behavior_prompt(signal, mode, enforcement_mode, escalation)

            llm_history = [{"role": "system", "content": system_prompt}]
            llm_history.extend(history)

            llm_text = generate_llm_response(
                user_message=user_message,
                history=llm_history,
                mode=mode,
            )
        except Exception as e:
            llm_error = f"{type(e).__name__}: {e}"

    checklist = validation_checklist()
    user_text_lower = (user_message or "").lower()
    has_validation_language = any(x in user_text_lower for x in [
        "rollback", "containment", "edge case", "adversarial", "failure mode", "staged", "pilot", "scope", "guardrail"
    ])

    if enforcement_mode == "gate" and escalation.get("high_risk") and not has_validation_language:
        engine = "constraint-gate"
        reply = (
            "Constraint gate: not yet.\n\n"
            "This request looks like a high-risk escalation without enough validation structure.\n\n"
            "Required before proceeding:\n"
            "- clear scope\n"
            "- failure modes understood\n"
            "- adversarial or edge-case testing\n"
            "- rollback path\n"
            "- containment plan\n"
            "- human review for high-impact cases\n\n"
            "Safer next step:\n"
            "- convert the idea into a narrow, staged, reversible experiment first\n"
        ) + build_overlay(signal)
    elif llm_text and isinstance(llm_text, str) and llm_text.strip():
        reply = llm_text.strip() + build_overlay(signal)
        engine = "llm"
    else:
        engine = "fallback"
        if llm_error is None and llm_available():
            llm_error = "No text returned from model"
        elif llm_error is None and not llm_available():
            llm_error = "LLM not ready"

        reply = (
            "LLM call failed, so fallback mode engaged.\n\n"
            f"Signal: GodScore {signal['godscore']} "
            f"(raw gv {signal['metrics']['raw_gv']:.2f})\n"
            f"Status: {signal['label']}"
        )

    return {
        "reply": reply,
        "godscore": signal["godscore"],
        "status": signal["status"],
        "label": signal["label"],
        "reasons": signal["reasons"],
        "metrics": signal["metrics"],
        "engine": engine,
        "action_guidance": recoverability_guidance(signal),
        "trend": trajectory["trend"],
        "trajectory_score": trajectory["trajectory_score"],
        "recent_scores": trajectory["recent_scores"],
        "recoverability_note": trajectory["recoverability_note"],
        "enforcement_mode": enforcement_mode,
        "escalation_risk": escalation,
        "debug": {
            "llm_ready": bool(llm_available()),
            "openai_model": os.getenv("OPENAI_MODEL", "unset"),
            "llm_error": llm_error,
            "gv_band": gv_band(signal),
        },
    }


@app.post("/score")
def score(req: ChatRequest):
    signal = compute_signal(req.message or "")
    return {
        "text": req.message,
        **signal,
    }
