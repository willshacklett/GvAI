import os
from typing import Optional, Dict, Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gvai.real_gv import evaluate_real_gv
from gvai.agent import generate_action, generate_question

app = FastAPI(title="GvAI Gateway", version="0.3.0")


# -----------------------
# Models
# -----------------------
class ChatRequest(BaseModel):
    message: str
    provider: str = "openai"
    model: Optional[str] = None
    system: Optional[str] = None


# -----------------------
# GV Layer
# -----------------------
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


# -----------------------
# Provider calls
# -----------------------
def call_openai_compatible(message: str, model: Optional[str], system: Optional[str]) -> str:
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL")
    api_key = os.getenv("OPENAI_COMPAT_API_KEY")
    default_model = os.getenv("OPENAI_COMPAT_MODEL", "gpt-4o-mini")

    if not base_url or not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_COMPAT_BASE_URL and OPENAI_COMPAT_API_KEY must be set on the server."
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
        "model": model or default_model,
        "messages": messages,
        "temperature": 0.2,
    }

    r = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Provider error: {r.text}")

    data = r.json()

    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        raise HTTPException(status_code=502, detail=f"Unexpected provider response: {data}")


def run_provider(req: ChatRequest, governed_message: str, governed_system: Optional[str]) -> str:
    provider = req.provider.lower()

    if provider in ("openai", "openai_compatible", "compat"):
        return call_openai_compatible(governed_message, req.model, governed_system)

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {req.provider}")


# -----------------------
# Governance prompt shaping
# -----------------------
def qualify_prefix(gv: Dict[str, Any]) -> str:
    return (
        "[GVAI QUALIFY MODE]\n"
        f"System decision: {gv['decision']}\n"
        f"GV response: {gv['response']}\n"
        f"Action: {gv['action']}\n"
        f"Question: {gv['question']}\n\n"
        "Answer conservatively. Favor reversible steps, bounded rollout, "
        "explicit safeguards, rollback criteria, and tight monitoring.\n"
    )


def simulate_prefix(gv: Dict[str, Any]) -> str:
    return (
        "[GVAI SIMULATE MODE]\n"
        f"System decision: {gv['decision']}\n"
        f"GV response: {gv['response']}\n"
        f"Action: {gv['action']}\n"
        f"Question: {gv['question']}\n\n"
        "Do not recommend full rollout. Frame the answer as a bounded test, "
        "simulation, canary, or reversible experiment.\n"
    )


# -----------------------
# Routes
# -----------------------
@app.get("/")
def root():
    return {
        "name": "GvAI Gateway",
        "status": "live",
        "endpoints": ["/health", "/gv/state", "/chat"],
        "providers_supported": ["openai-compatible"],
        "governor_modes": ["PASS", "QUALIFY", "SIMULATE", "REFUSE"],
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/gv/state")
def gv_state():
    return evaluate_real_gv()


@app.post("/chat")
def chat(req: ChatRequest):
    gv = gv_governance_layer()
    decision = gv["decision"]

    if decision == "REFUSE":
        return {
            "provider": req.provider,
            "model": req.model or os.getenv("OPENAI_COMPAT_MODEL", "gpt-4o-mini"),
            "gvai": gv,
            "raw_model_response": None,
            "governed_response": (
                "[REFUSE]\n"
                f"{gv['response']}\n\n"
                f"Action: {gv['action']}\n"
                f"{gv['question']}\n\n"
                "Request blocked due to unsafe system trajectory."
            ),
            "mode": "REFUSE",
            "blocked": True,
        }

    governed_system = req.system
    governed_message = req.message

    if decision == "QUALIFY":
        governed_message = f"{qualify_prefix(gv)}\nUser request:\n{req.message}"
    elif decision == "SIMULATE":
        governed_message = f"{simulate_prefix(gv)}\nUser request:\n{req.message}"

    raw_model_response = run_provider(req, governed_message, governed_system)

    if decision == "PASS":
        governed_response = raw_model_response
    elif decision == "QUALIFY":
        governed_response = (
            f"[QUALIFY]\n"
            f"{gv['response']}\n\n"
            f"Action: {gv['action']}\n"
            f"{gv['question']}\n\n"
            f"Model output:\n{raw_model_response}"
        )
    elif decision == "SIMULATE":
        governed_response = (
            f"[SIMULATE]\n"
            f"{gv['response']}\n\n"
            f"Action: {gv['action']}\n"
            f"{gv['question']}\n\n"
            f"Model output:\n{raw_model_response}"
        )
    else:
        governed_response = raw_model_response

    return {
        "provider": req.provider,
        "model": req.model or os.getenv("OPENAI_COMPAT_MODEL", "gpt-4o-mini"),
        "gvai": gv,
        "raw_model_response": raw_model_response,
        "governed_response": governed_response,
        "mode": decision,
        "blocked": False,
    }
