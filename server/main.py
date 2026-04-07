from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import os

app = FastAPI(title="GvAI API", version="1.3.0")

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

try:
    from gvai.llm import generate_llm_response, llm_available
except Exception:
    generate_llm_response = None
    def llm_available() -> bool:
        return False

def fallback_score(message: str) -> Dict[str, Any]:
    words = len(message.split())
    chars = len(message.strip())
    base = 78
    if chars > 0:
        base += min(8, chars // 40)
    if "?" in message:
        base += 2
    if len(words := message.split()) >= 8:
        base += 3

    score = max(55, min(99, base))
    status = "stable" if score >= 85 else "watch"
    return {
        "godscore": score,
        "status": status,
        "label": "unknown" if status != "stable" else "stable",
        "metrics": {
            "chars": chars,
            "words": len(words),
            "raw_gv": float(score),
        },
    }

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "gvai-api",
        "llm_loaded": generate_llm_response is not None,
        "llm_ready": bool(llm_available()),
        "openai_model": os.getenv("OPENAI_MODEL", "unset"),
    }

@app.post("/api/chat")
def api_chat(req: ChatRequest):
    user_message = (req.message or "").strip()
    history = req.history or []
    mode = (req.mode or "simple").strip()

    if not user_message:
        return {
            "reply": "No message received.",
            "engine": "none",
            "debug": {"error": "empty_message"},
        }

    score_payload = fallback_score(user_message)

    llm_text = None
    llm_error = None

    if generate_llm_response is not None:
        try:
            llm_text = generate_llm_response(
                user_message=user_message,
                history=history,
                mode=mode,
            )
        except Exception as e:
            llm_error = f"{type(e).__name__}: {e}"

    if llm_text and llm_text.strip():
        decision = "stable" if score_payload["godscore"] >= 85 else "watch"
        return {
            "reply": (
                f"{llm_text.strip()}\n\n"
                f"---\n"
                f"Signal: GodScore {score_payload['godscore']} "
                f"(raw gv {score_payload['metrics']['raw_gv']:.2f})\n"
                f"Status: {score_payload['label']} | Decision: {decision}"
            ),
            "godscore": score_payload["godscore"],
            "status": score_payload["status"],
            "label": score_payload["label"],
            "metrics": score_payload["metrics"],
            "engine": "llm",
            "debug": {
                "llm_ready": bool(llm_available()),
                "openai_model": os.getenv("OPENAI_MODEL", "unset"),
                "llm_error": None,
            },
        }

    return {
        "reply": (
            "LLM call failed, so fallback mode engaged.\n\n"
            f"Signal: GodScore {score_payload['godscore']} "
            f"(raw gv {score_payload['metrics']['raw_gv']:.2f})\n"
            f"Status: {score_payload['label']}"
        ),
        "godscore": score_payload["godscore"],
        "status": score_payload["status"],
        "label": score_payload["label"],
        "metrics": score_payload["metrics"],
        "engine": "fallback",
        "debug": {
            "llm_ready": bool(llm_available()),
            "openai_model": os.getenv("OPENAI_MODEL", "unset"),
            "llm_error": llm_error or "No text returned from model",
        },
    }
