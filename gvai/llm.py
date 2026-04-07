from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from openai import OpenAI


def llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _build_messages(
    user_message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    mode: str = "simple",
) -> List[Dict[str, str]]:
    system = (
        "You are GvAI, a survivability-native intelligence system. "
        "Be concise, practical, and structured. "
        "Prefer stability analysis, recoverability, risk framing, and clear next steps. "
        "Do not claim certainty you do not have. "
        "Answer like a useful assistant first, then let the signal layer annotate the response."
    )

    if mode == "dramatic":
        system += " Use elevated but readable prose."
    elif mode == "explain":
        system += " Favor plain-English explanation and step-by-step clarity."
    else:
        system += " Favor a short clean answer first, then compact rationale."

    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]

    if history:
        for item in history[-12:]:
            role = str(item.get("role", "user"))
            content = str(item.get("content", "")).strip()
            if role in {"system", "user", "assistant"} and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message})
    return messages


def generate_llm_response(
    user_message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    mode: str = "simple",
) -> str:
    if not llm_available():
        raise RuntimeError("OPENAI_API_KEY is missing")

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    messages = _build_messages(user_message=user_message, history=history, mode=mode)

    # First try Chat Completions
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.4,
        )
        text = resp.choices[0].message.content
        if isinstance(text, str) and text.strip():
            return text.strip()
    except Exception as e:
        chat_error = f"{type(e).__name__}: {e}"
    else:
        chat_error = "No text returned from chat.completions"

    # Fallback to Responses API
    try:
        input_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        resp = client.responses.create(
            model=model,
            input=input_text,
            temperature=0.4,
        )
        text = getattr(resp, "output_text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    except Exception as e:
        resp_error = f"{type(e).__name__}: {e}"
    else:
        resp_error = "No text returned from responses.create"

    raise RuntimeError(
        f"LLM failed. chat.completions -> {chat_error} | responses.create -> {resp_error}"
    )
