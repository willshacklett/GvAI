from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None


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
        "If the user asks a broad general question, still answer helpfully, but stay grounded. "
    )

    if mode == "dramatic":
        system += "Use elevated but still readable prose. "
    elif mode == "explain":
        system += "Favor plain-English explanation and step-by-step clarity. "
    else:
        system += "Favor a short clean answer first, then a compact rationale. "

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
) -> Optional[str]:
    if not llm_available():
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    messages = _build_messages(user_message=user_message, history=history, mode=mode)

    try:
        # Works with the common chat-completions style SDK.
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.4,
        )
        text = resp.choices[0].message.content
        if isinstance(text, str) and text.strip():
            return text.strip()
    except Exception:
        return None

    return None
