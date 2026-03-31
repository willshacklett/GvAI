import sys
from gvai.core import GvCore
from gvai.memory import GvMemory
from gvai.agent import generate_response


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
    if len(sys.argv) < 2:
        print('Usage: python -m gvai.cli "your text here"')
        return

    gv = GvCore()
    memory = GvMemory()

    inputs = sys.argv[1:]

    for text in inputs:
        result = gv.evaluate(text)
        memory.add(result)
        m = result["metrics"]

        trend = memory.trend()
        volatility = memory.volatility()
        decision = escalate_decision(result["decision"], trend, volatility, m)

        response = generate_response(text, decision, m)

        print("\n=== GvAI ===")
        print(f"Input: {text}")
        print(f"Decision: {decision}")
        print(f"Response: {response}")

        print("\nTrajectory:")
        print(f"Trend: {trend}")
        print(f"Volatility: {volatility}")

        print("\nMetrics:")
        print(f"Gv Score: {m['gv_score']}")
        print(f"Confidence Stability: {m['confidence_stability']}")


if __name__ == "__main__":
    main()
