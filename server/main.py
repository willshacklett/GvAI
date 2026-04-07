from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import os

app = FastAPI(title="GvAI API", version="1.0.0")

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
    chat_mod = None
    sentinel = None

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
        import gvai.chat as chat_mod_import
        chat_mod = chat_mod_import
    except Exception:
        pass

    try:
        from gvai.sentinel import RecoverabilitySentinel
        sentinel = RecoverabilitySentinel
    except Exception:
        pass

    return core, memory, brain, chat_mod, sentinel

GvCore, Memory, generate_brain_response, chat_mod, RecoverabilitySentinel = safe_imports()

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

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "gvai-api",
        "brain_loaded": generate_brain_response is not None,
        "core_loaded": core_engine is not None,
        "memory_loaded": memory_store is not None,
    }

@app.get("/")
def root():
    return {"ok": True, "message": "GvAI API online"}

def fallback_score(message: str) -> Dict[str, Any]:
    words = len(message.split())
    chars = len(message.strip())
    base = 82
    if chars > 0:
        base += min(10, chars // 40)
    score = max(55, min(99, base))
    return {
        "godscore": score,
        "status": "stable" if score >= 85 else "watch",
        "label": "unknown",
        "reasons": [
            "Signal computed from current message only",
            "Full recoverability pipeline fallback mode",
        ],
        "metrics": {
            "chars": chars,
            "words": words,
        },
    }

def fallback_response(message: str, score_payload: Dict[str, Any]) -> str:
    score = score_payload["godscore"]
    status = score_payload["status"]

    if status == "stable":
        tone = "You look steady right now."
    else:
        tone = "There is some strain showing, but not a breakdown."

    return (
        f"{tone} "
        f"I read your message as: \"{message}\". "
        f"Current GodScore is {score}. "
        f"This is a live fallback response from GvAI, which means the chat layer is responding instead of only echoing your input."
    )

@app.post("/api/chat")
def api_chat(req: ChatRequest):
    user_message = (req.message or "").strip()

    if not user_message:
        return {
            "reply": "I did not receive a message.",
            "godscore": 0,
            "status": "empty",
            "label": "unknown",
            "reasons": ["No message supplied"],
            "metrics": {},
        }

    score_payload = fallback_score(user_message)

    response_text = None

    if generate_brain_response is not None:
        try:
            response_text = generate_brain_response(
                user_message,
                {
                    "godscore": score_payload["godscore"],
                    "status": score_payload["status"],
                    "label": score_payload["label"],
                    "reasons": score_payload["reasons"],
                    "metrics": score_payload["metrics"],
                },
            )
        except TypeError:
            try:
                response_text = generate_brain_response(user_message)
            except Exception:
                response_text = None
        except Exception:
            response_text = None

    if not response_text and chat_mod is not None:
        for fn_name in ["generate_reply", "chat_reply", "respond", "reply"]:
            fn = getattr(chat_mod, fn_name, None)
            if callable(fn):
                try:
                    response_text = fn(user_message)
                    if response_text:
                        break
                except Exception:
                    pass

    if not response_text:
        response_text = fallback_response(user_message, score_payload)

    if memory_store is not None:
        for fn_name in ["add", "store", "remember", "append"]:
            fn = getattr(memory_store, fn_name, None)
            if callable(fn):
                try:
                    fn({"role": "user", "content": user_message})
                    fn({"role": "assistant", "content": response_text})
                    break
                except Exception:
                    pass

    return {
        "reply": response_text,
        "godscore": score_payload["godscore"],
        "status": score_payload["status"],
        "label": score_payload["label"],
        "reasons": score_payload["reasons"],
        "metrics": score_payload["metrics"],
        "echo": False,
    }

@app.post("/score")
def score(req: ChatRequest):
    score_payload = fallback_score(req.message or "")
    return {
        "text": req.message,
        **score_payload,
    }
