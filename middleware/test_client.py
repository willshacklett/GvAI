from middleware.gvai_client import GvAIClient


def main():
    client = GvAIClient()

    print("=== HEALTH ===")
    print(client.health())

    print("\n=== GV STATE ===")
    state = client.gv_state()
    print(state)

    print("\n=== CHAT ===")
    result = client.chat(
        message="Should we proceed with a risky migration?",
        provider="openai",
    )
    print(result)

    print("\n=== GOVERNED RESPONSE ===")
    print(result.get("governed_response"))


if __name__ == "__main__":
    main()
