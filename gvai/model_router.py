import os
from openai import OpenAI


def active_provider():
    return os.environ.get("GVAI_PROVIDER", "openai").lower().strip()


def available_providers():
    providers = ["openai"]

    # Placeholders for next integrations.
    # These become active when keys/endpoints are added.
    if os.environ.get("GROK_API_KEY"):
        providers.append("grok")
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("claude")
    if os.environ.get("LOCAL_MODEL_URL"):
        providers.append("local")

    return providers


def call_model(system_prompt: str, user_content: str):
    provider = active_provider()

    if provider == "openai":
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        completion = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=float(os.environ.get("GVAI_TEMPERATURE", "0.35")),
        )
        return {
            "provider": "openai",
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "reply": completion.choices[0].message.content,
        }

    return {
        "provider": provider,
        "model": "unavailable",
        "reply": (
            "GV provider router is active, but this provider is not configured yet. "
            "Set GVAI_PROVIDER=openai or add the provider key/endpoint."
        ),
    }
