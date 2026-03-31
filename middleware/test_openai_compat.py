import os
from middleware.openai_compat import OpenAI


def main():
    client = OpenAI(
        base_url=os.getenv("GVAI_GATEWAY_URL", "http://127.0.0.1:8010")
    )

    print("=== HEALTH ===")
    print(client.health())

    print("\n=== GV STATE ===")
    print(client.gv_state())

    print("\n=== OPENAI-STYLE CALL ===")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Be concise and operational."},
            {"role": "user", "content": "Should we proceed with a risky migration?"},
        ],
        provider="openai",
    )

    print("\nMode:", resp.gvai.mode)
    print("Blocked:", resp.gvai.blocked)
    print("\nAssistant content:\n")
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    main()
