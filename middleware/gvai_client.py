import os
from typing import Any, Dict, Optional

import requests


DEFAULT_GATEWAY_URL = os.getenv("GVAI_GATEWAY_URL", "http://127.0.0.1:8010")


class GvAIClient:
    def __init__(self, gateway_url: Optional[str] = None, timeout: int = 120):
        self.gateway_url = (gateway_url or DEFAULT_GATEWAY_URL).rstrip("/")
        self.timeout = timeout

    def health(self) -> Dict[str, Any]:
        r = requests.get(f"{self.gateway_url}/health", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def gv_state(self) -> Dict[str, Any]:
        r = requests.get(f"{self.gateway_url}/gv/state", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def chat(
        self,
        message: str,
        provider: str = "openai",
        model: Optional[str] = None,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "message": message,
            "provider": provider,
        }
        if model:
            payload["model"] = model
        if system:
            payload["system"] = system

        r = requests.post(
            f"{self.gateway_url}/chat",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def guarded_chat(
        self,
        message: str,
        provider: str = "openai",
        model: Optional[str] = None,
        system: Optional[str] = None,
    ) -> str:
        result = self.chat(message=message, provider=provider, model=model, system=system)
        return result.get("governed_response") or result.get("raw_model_response") or ""
