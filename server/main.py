from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="GvAI API", version="1.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = None
    mode: Optional[str] = "simple"

from gvai.llm import generate_llm_response, llm_available


def compute_signal(message: str) -> Dict[str, Any]:
    text = (message or "").strip()
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

    reasons = ["Signal computed from current message only"]
    if len(words) < 8:
        reasons.append("Compact prompt with limited context")
    else:
        reasons.append("Prompt includes enough structure for a richer answer")

    metrics = {
        "chars": chars,
        "words": len(words),
        "raw_gv": float(godscore),
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
        "llm_loaded": True,
        "llm_ready": bool(llm_available()),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    }


@app.get("/api/chat")
def api_chat_get():
    return {
        "ok": True,
        "message": 'Use POST /api/chat with JSON like {"message":"...","history":[],"mode":"simple"}'
    }


@app.post("/api/chat")
def api_chat(req: ChatRequest):
    user_message = (req.message or "").strip()
    history = req.history or []
    mode = (req.mode or "simple").strip()

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
                "llm_error": "empty_message",
            },
        }

    signal = compute_signal(user_message)

    try:
        llm_text = generate_llm_response(
            user_message=user_message,
            history=history,
            mode=mode,
        )
        return {
            "reply": llm_text.strip() + build_overlay(signal),
            "godscore": signal["godscore"],
            "status": signal["status"],
            "label": signal["label"],
            "reasons": signal["reasons"],
            "metrics": signal["metrics"],
            "engine": "llm",
            "debug": {
                "llm_ready": bool(llm_available()),
                "openai_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                "llm_error": None,
            },
        }
    except Exception as e:
        return {
            "reply": (
                "LLM failed, so fallback mode engaged.\n\n"
                f"Signal: GodScore {signal['godscore']} "
                f"(raw gv {signal['metrics']['raw_gv']:.2f})\n"
                f"Status: {signal['label']}\n\n"
                f"LLM error: {type(e).__name__}: {e}"
            ),
            "godscore": signal["godscore"],
            "status": signal["status"],
            "label": signal["label"],
            "reasons": signal["reasons"],
            "metrics": signal["metrics"],
            "engine": "fallback",
            "debug": {
                "llm_ready": bool(llm_available()),
                "openai_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                "llm_error": f"{type(e).__name__}: {e}",
            },
        }


@app.post("/score")
def score(req: ChatRequest):
    signal = compute_signal(req.message or "")
    return {
        "text": req.message,
        **signal,
    }
