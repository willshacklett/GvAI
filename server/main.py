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


def coerce_request_context(req: ChatRequest) -> tuple[str, List[Dict[str, str]], str]:
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

    return user_message, history, mode

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
    user_message, history, mode = coerce_request_context(req)

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

    llm_text = None
    llm_error = None

    if generate_llm_response is not None and llm_available():
        try:
            llm_text = generate_llm_response(
                user_message=user_message,
                history=history,
                mode=mode,
            )
        except Exception as e:
            llm_error = f"{type(e).__name__}: {e}"

    if llm_text and isinstance(llm_text, str) and llm_text.strip():
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
        "debug": {
            "llm_ready": bool(llm_available()),
            "openai_model": os.getenv("OPENAI_MODEL", "unset"),
            "llm_error": llm_error,
        },
    }


@app.post("/score")
def score(req: ChatRequest):
    signal = compute_signal(req.message or "")
    return {
        "text": req.message,
        **signal,
    }
