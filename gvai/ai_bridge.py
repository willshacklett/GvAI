from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import requests

from privacy.egress import authorize_external_model


def _authorize_ai_egress(payload: Dict[str, Any], provider: str) -> None:
    """
    Final GVAI privacy checkpoint immediately before an external
    model transmission.

    Current compatibility behavior:
      * Standard GVAI mode -> external AI allowed.
      * Private Build Mode -> external AI denied.
      * Explicitly shared + consent -> may leave.

    Later the data classification will come from the authenticated
    user/project/request rather than the environment.
    """

    private_mode = os.getenv(
        "GVAI_PRIVATE_BUILD_MODE",
        "0"
    ).strip().lower() in {"1", "true", "yes", "on"}

    # Preserve existing GVAI behavior outside Private Build Mode.
    #
    # In Private Build Mode the privacy router itself still fails
    # closed, including for PUBLIC content, unless the user explicitly
    # shares it with consent.
    data_class = os.getenv(
        "GVAI_DATA_CLASS",
        "private" if private_mode else "public"
    )

    authorize_external_model(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        ),
        provider=provider,
        data_class=data_class,
        private_build_mode=private_mode,
    )



def _normalize_messages(system_prompt: str | None, messages: List[Dict[str, str]] | None, message: str | None) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []

    if system_prompt:
        normalized.append({"role": "system", "content": system_prompt})

    if messages:
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if content:
                normalized.append({"role": role, "content": content})

    if message:
        normalized.append({"role": "user", "content": message})

    return normalized


def chat_openai(message: str | None = None, *, messages: List[Dict[str, str]] | None = None, system_prompt: str | None = None, model: str | None = None) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "messages": _normalize_messages(system_prompt, messages, message),
    }

    _authorize_ai_egress(payload, "openai")

    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    res.raise_for_status()
    data = res.json()
    reply = data["choices"][0]["message"]["content"]
    return {"provider": "openai", "model": model, "reply": reply, "raw": data}


def chat_xai(message: str | None = None, *, messages: List[Dict[str, str]] | None = None, system_prompt: str | None = None, model: str | None = None) -> Dict[str, Any]:
    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("XAI_API_KEY not configured")

    model = model or os.getenv("XAI_MODEL", "grok-2-latest")
    payload = {
        "model": model,
        "messages": _normalize_messages(system_prompt, messages, message),
    }

    _authorize_ai_egress(payload, "xai")

    res = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    res.raise_for_status()
    data = res.json()
    reply = data["choices"][0]["message"]["content"]
    return {"provider": "xai", "model": model, "reply": reply, "raw": data}


def chat_anthropic(message: str | None = None, *, messages: List[Dict[str, str]] | None = None, system_prompt: str | None = None, model: str | None = None) -> Dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")

    model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    normalized = _normalize_messages(None, messages, message)
    anthropic_messages = []
    for m in normalized:
        if m["role"] == "system":
            continue
        anthropic_messages.append({"role": "assistant" if m["role"] == "assistant" else "user", "content": m["content"]})

    payload = {
        "model": model,
        "max_tokens": 1200,
        "messages": anthropic_messages,
    }
    if system_prompt:
        payload["system"] = system_prompt

    _authorize_ai_egress(payload, "anthropic")

    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    res.raise_for_status()
    data = res.json()

    parts = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    reply = "\n".join(parts).strip()

    return {"provider": "anthropic", "model": model, "reply": reply, "raw": data}


def available_providers() -> List[str]:
    providers = []
    if os.getenv("OPENAI_API_KEY", "").strip():
        providers.append("openai")
    if os.getenv("XAI_API_KEY", "").strip():
        providers.append("xai")
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        providers.append("anthropic")
    return providers


def chat_provider(provider: str, message: str | None = None, *, messages: List[Dict[str, str]] | None = None, system_prompt: str | None = None, model: str | None = None) -> Dict[str, Any]:
    provider = (provider or "").strip().lower()

    if provider == "openai":
        return chat_openai(message, messages=messages, system_prompt=system_prompt, model=model)
    if provider in {"xai", "grok"}:
        return chat_xai(message, messages=messages, system_prompt=system_prompt, model=model)
    if provider in {"anthropic", "claude"}:
        return chat_anthropic(message, messages=messages, system_prompt=system_prompt, model=model)

    raise RuntimeError(f"Unknown provider: {provider}")
