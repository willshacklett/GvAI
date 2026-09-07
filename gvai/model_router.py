import os
from openai import OpenAI

from privacy.egress import authorize_external_model


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
        payload = {
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }

        authorize_external_model(
            str(payload),
            provider="openai",
            data_class=(
                os.getenv("GVAI_DATA_CLASS")
                or (
                    "private"
                    if os.getenv("GVAI_PRIVATE_BUILD_MODE", "0").lower()
                    in {"1", "true", "yes", "on"}
                    else "public"
                )
            ),
        )

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
