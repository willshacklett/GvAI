from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

app = FastAPI(title="GvAI API", version="1.2.0")

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

# --- import LLM ---
try:
    from gvai.llm import generate_llm_response
except Exception:
    generate_llm_response = None

def fallback_score(message: str) -> Dict[str, Any]:
    words = len(message.split())
    chars = len(message.strip())
    base = 78

    if chars > 0:
        base += min(8, chars // 40)
    if "?" in message:
        base += 2
    if len(message.split()) >= 8:
        base += 3

    score = max(55, min(99, base))
    status = "stable" if score >= 85 else "watch"

    return {
        "godscore": score,
        "status": status,
        "label": "unknown" if status != "stable" else "stable",
        "metrics": {
            "chars": chars,
            "words": words,
            "raw_gv": float(score),
        },
    }

# 🔥 NEW: LLM-FIRST RESPONSE
def governed_response(
    user_message: str,
    llm_text: Optional[str],
    score_payload: Dict[str, Any],
) -> str:

    if llm_text:
        decision = "stable" if score_payload["godscore"] >= 85 else "watch"

        return (
            f"{llm_text.strip()}\n\n"
            f"---\n"
            f"Signal: GodScore {score_payload['godscore']} "
            f"(raw gv {score_payload['metrics']['raw_gv']:.2f})\n"
            f"Status: {score_payload['label']} | Decision: {decision}"
        )

    return "LLM unavailable — fallback engaged."

@app.post("/api/chat")
def api_chat(req: ChatRequest):
    user_message = (req.message or "").strip()

    if not user_message:
        return {"reply": "No message received."}

    score_payload = fallback_score(user_message)

    llm_text = None
    if generate_llm_response is not None:
        try:
            llm_text = generate_llm_response(user_message)
        except Exception:
            llm_text = None

    response_text = governed_response(
        user_message,
        llm_text,
        score_payload
    )

    return {
        "reply": response_text,
        "godscore": score_payload["godscore"],
        "status": score_payload["status"],
        "label": score_payload["label"],
        "metrics": score_payload["metrics"],
        "engine": "llm" if llm_text else "fallback",
    }

@app.get("/health")
def health():
    llm_ready = False
    try:
        from gvai.llm import llm_available
        llm_ready = llm_available()
    except:
        pass

    return {
        "ok": True,
        "llm_ready": llm_ready
    }
