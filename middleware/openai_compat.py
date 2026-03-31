import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from middleware.gvai_client import GvAIClient


def _dict_to_ns(obj: Any) -> Any:
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _dict_to_ns(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_dict_to_ns(x) for x in obj]
    return obj


class _ChatCompletions:
    def __init__(self, client: GvAIClient):
        self._client = client

    def create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        provider: str = "openai",
        **kwargs,
    ):
        system_parts = []
        user_parts = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                user_parts.append(content)
            else:
                user_parts.append(f"[{role}] {content}")

        system = "\n\n".join(system_parts) if system_parts else None
        message = "\n\n".join(user_parts).strip()

        result = self._client.chat(
            message=message,
            provider=provider,
            model=model,
            system=system,
        )

        content = (
            result.get("governed_response")
            or result.get("raw_model_response")
            or ""
        )

        response = {
            "id": "gvai-chatcmpl-1",
            "object": "chat.completion",
            "created": 0,
            "model": result.get("model", model),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "gvai": {
                "mode": result.get("mode"),
                "blocked": result.get("blocked"),
                "state": result.get("gvai"),
            },
            "raw": result,
        }

        return _dict_to_ns(response)


class _Chat:
    def __init__(self, client: GvAIClient):
        self.completions = _ChatCompletions(client)


class OpenAI:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 120,
        api_key: Optional[str] = None,
    ):
        gateway_url = base_url or os.getenv("GVAI_GATEWAY_URL", "http://127.0.0.1:8010")
        self._gvai = GvAIClient(gateway_url=gateway_url, timeout=timeout)
        self.api_key = api_key
        self.chat = _Chat(self._gvai)

    def health(self):
        return self._gvai.health()

    def gv_state(self):
        return self._gvai.gv_state()
