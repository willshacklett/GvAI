from gvai.core import GvCore
from gvai.memory import GvMemory
from gvai.brain import generate_brain_response


def escalate_decision(base_decision, trend, volatility, metrics):
    score = metrics["gv_score"]

    if base_decision == "REFUSE":
        return "REFUSE"

    if trend == "DEGRADING" and volatility >= 0.25:
        if score < 0.55:
            return "REFUSE"
        return "SIMULATE"

    if trend == "DEGRADING" and volatility >= 0.12:
        if base_decision == "PASS":
            return "QUALIFY"
        if base_decision == "QUALIFY":
            return "SIMULATE"

    return base_decision


def main():
    gv = GvCore()
    memory = GvMemory()

    print("GvAI Chat (type 'exit' to quit)\n")

    while True:
        user_input = input("You: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        result = gv.evaluate(user_input)
        memory.add(result)
        m = result["metrics"]

        trend = memory.trend()
        volatility = memory.volatility()

        decision = escalate_decision(result["decision"], trend, volatility, m)

        response = generate_brain_response(user_input, decision, m, trend, volatility)

        print("\nGvAI:")
        print(f"[{decision}] {response}")
        print(f"(Trend: {trend}, Volatility: {volatility})\n")


if __name__ == "__main__":
    main()
