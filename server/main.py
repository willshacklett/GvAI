from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import traceback

app = FastAPI(title="GvAI API", version="1.1.0")

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

def safe_imports():
    core = None
    memory = None
    brain = None
    llm_fn = None

    try:
        from gvai.core import GvCore
        core = GvCore
    except Exception:
        pass

    try:
        from gvai.memory import Memory
        memory = Memory
    except Exception:
        pass

    try:
        from gvai.brain import generate_brain_response
        brain = generate_brain_response
    except Exception:
        pass

    try:
        from gvai.llm import generate_llm_response
        llm_fn = generate_llm_response
    except Exception:
        pass

    return core, memory, brain, llm_fn

GvCore, Memory, generate_brain_response, generate_llm_response = safe_imports()

memory_store = None
if Memory is not None:
    try:
        memory_store = Memory()
    except Exception:
        memory_store = None

core_engine = None
if GvCore is not None:
    try:
        core_engine = GvCore()
    except Exception:
        core_engine = None

@app.get("/")
def root():
    return {"ok": True, "message": "GvAI API online"}

@app.get("/health")
def health():
    llm_ready = False
    try:
        from gvai.llm import llm_available
        llm_ready = bool(llm_available())
    except Exception:
        llm_ready = False

    return {
        "ok": True,
        "service": "gvai-api",
        "brain_loaded": generate_brain_response is not None,
        "core_loaded": core_engine is not None,
        "memory_loaded": memory_store is not None,
        "llm_loaded": generate_llm_response is not None,
        "llm_ready": llm_ready,
    }

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
        "reasons": [
            "Signal computed from current message only",
            "Full recoverability pipeline fallback mode",
        ],
        "metrics": {
            "chars": chars,
            "words": words,
            "raw_gv": float(score),
        },
    }

def governed_response(
    user_message: str,
    llm_text: Optional[str],
    score_payload: Dict[str, Any],
    mode: str = "simple",
) -> str:
    if llm_text and generate_brain_response is not None:
        try:
            wrapped = {
                "godscore": score_payload["godscore"],
                "status": score_payload["status"],
                "label": score_payload["label"],
                "reasons": score_payload["reasons"],
                "metrics": score_payload["metrics"],
                "draft_response": llm_text,
            }
            out = generate_brain_response(user_message, wrapped)
            if isinstance(out, str) and out.strip():
                return out.strip()
        except Exception:
            pass

    if llm_text:
        return llm_text.strip()

    decision = "stable" if score_payload["godscore"] >= 85 else "watch"
    intro = {
        "simple": f"Short answer: this message was {score_payload['label']}.",
        "explain": f"Simple explanation: I read this as {score_payload['label']}.",
        "dramatic": f"The signal reads {score_payload['label']}, not collapsed but not settled.",
    }.get(mode or "simple", f"Short answer: this message was {score_payload['label']}.")

    why = "\n".join(f"- {r}" for r in score_payload["reasons"])
    return (
        f"{intro}\n\n"
        f"Signal read: GodScore {score_payload['godscore']} "
        f"(raw gv {score_payload['metrics'].get('raw_gv', score_payload['godscore']):.2f}); "
        f"status {score_payload['label']}.\n\n"
        f"Why:\n"
        f"- decision: {decision}\n"
        f"- raw gv: {score_payload['metrics'].get('raw_gv', score_payload['godscore']):.2f}\n"
        f"{why}"
    )

def store_memory(user_message: str, assistant_message: str):
    if memory_store is None:
        return

    for fn_name in ["add", "store", "remember", "append"]:
        fn = getattr(memory_store, fn_name, None)
        if callable(fn):
            try:
                fn({"role": "user", "content": user_message})
                fn({"role": "assistant", "content": assistant_message})
                return
            except Exception:
                pass

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
        }

    score_payload = fallback_score(user_message)

    llm_text = None
    engine = "fallback"

    if generate_llm_response is not None:
        try:
            llm_text = generate_llm_response(
                user_message=user_message,
                history=history,
                mode=mode,
            )
            if llm_text:
                engine = "llm"
        except Exception:
            llm_text = None
            engine = "fallback"

    response_text = governed_response(
        user_message=user_message,
        llm_text=llm_text,
        score_payload=score_payload,
        mode=mode,
    )

    store_memory(user_message, response_text)

    return {
        "reply": response_text,
        "godscore": score_payload["godscore"],
        "status": score_payload["status"],
        "label": score_payload["label"],
        "reasons": score_payload["reasons"],
        "metrics": score_payload["metrics"],
        "engine": engine,
        "echo": False,
    }

@app.get("/api/chat")
def api_chat_get():
    return {
        "ok": True,
        "message": "Use POST /api/chat with JSON: {\"message\":\"...\",\"history\":[],\"mode\":\"simple\"}",
    }

@app.post("/score")
def score(req: ChatRequest):
    score_payload = fallback_score(req.message or "")
    return {
        "text": req.message,
        **score_payload,
    }
