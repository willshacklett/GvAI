from middleware.gvai_client import GvAIClient


client = GvAIClient()


def run_task(user_request: str):
    result = client.chat(user_request, provider="openai")

    mode = result.get("mode")
    blocked = result.get("blocked", False)

    print(f"Mode: {mode}")
    print(f"Blocked: {blocked}")
    print()
    print(result.get("governed_response"))

    return result


if __name__ == "__main__":
    run_task("Should we proceed with a risky migration?")
