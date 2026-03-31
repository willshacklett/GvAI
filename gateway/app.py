import os
from typing import Optional, Dict, Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gvai.real_gv import evaluate_real_gv
from gvai.agent import generate_action, generate_question


app = FastAPI(title="GvAI Gateway", version="0.1.0")


class ChatRequest(BaseModel):
    message: str
    provider: str = "ollama"
    model: Optional[str] = None
    system: Optional[str] = None


def gv_governance_layer() -> Dict[str, Any]:
    result = evaluate_real_gv()
    summary = result["summary"]
    decision = result["decision"]

    return {
        "decision": decision,
        "response": result["response"],
        "action": generate_action(summary, decision),
        "question": generate_question(summary, decision),
        "summary": summary,
    }


def call_ollama(message: str, model: str, system: Optional[str] = None) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    payload = {
        "model": model or os.getenv("OLLAMA_MODEL", "llama3.1"),
        "prompt": message,
        "stream": False,
    }
    if system:
        payload["system"] = system

    r = requests.post(f"{base_url}/api/generate", json=payload, timeout=120)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Ollama error: {r.text}")
    data = r.json()
    return data.get("response", "").strip()


def call_openai_compatible(message: str, model: str, system: Optional[str] = None) -> str:
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL")
    api_key = os.getenv("OPENAI_COMPAT_API_KEY")

    if not base_url or not api_key:
        raise HTTPException(
            status_code=400,
            detail="OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_API_KEY must be set.",
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": model or os.getenv("OPENAI_COMPAT_MODEL", "gpt-4o-mini"),
        "messages": messages,
        "temperature": 0.2,
    }

    r = requests.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=120)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"OpenAI-compatible error: {r.text}")

    data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        raise HTTPException(status_code=502, detail=f"Unexpected provider response: {data}")


def run_provider(req: ChatRequest) -> str:
    provider = req.provider.lower()

    if provider == "ollama":
        return call_ollama(req.message, req.model or "", req.system)

    if provider in ("openai", "openai_compatible", "compat"):
        return call_openai_compatible(req.message, req.model or "", req.system)

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {req.provider}")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/gv/state")
def gv_state():
    return gv_governance_layer()


@app.post("/chat")
def chat(req: ChatRequest):
    gv = gv_governance_layer()

    raw_model_response = run_provider(req)

    decision = gv["decision"]
    governed_prefix = {
        "PASS": "PASS",
        "QUALIFY": "QUALIFY",
        "SIMULATE": "SIMULATE",
        "REFUSE": "REFUSE",
    }.get(decision, "UNKNOWN")

    governed_response = {
        "PASS": raw_model_response,
        "QUALIFY": (
            f"[QUALIFY]\n{gv['response']}\n\n"
            f"Action: {gv['action']}\n"
            f"{gv['question']}\n\n"
            f"Model output:\n{raw_model_response}"
        ),
        "SIMULATE": (
            f"[SIMULATE]\n{gv['response']}\n\n"
            f"Action: {gv['action']}\n"
            f"{gv['question']}\n\n"
            f"Model output held behind simulation recommendation:\n{raw_model_response}"
        ),
        "REFUSE": (
            f"[REFUSE]\n{gv['response']}\n\n"
            f"Action: {gv['action']}\n"
            f"{gv['question']}\n\n"
            f"Model output was generated but the current system state does not support safe continuation."
        ),
    }.get(decision, raw_model_response)

    return {
        "provider": req.provider,
        "model": req.model,
        "gvai": gv,
        "raw_model_response": raw_model_response,
        "governed_response": governed_response,
        "mode": governed_prefix,
    }
