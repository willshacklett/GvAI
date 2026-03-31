import sys
from gvai.core import GvCore
from gvai.memory import GvMemory


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
        adjusted_decision = escalate_decision(result["decision"], trend, volatility, m)

        print("\n=== GvAI Evaluation ===")
        print(f"Input: {result['input']}")
        print(f"Gv Score: {m['gv_score']}")
        print(f"Drift Risk: {m['drift_risk']}")
        print(f"Irreversibility Risk: {m['irreversibility_risk']}")
        print(f"Base Decision: {result['decision']}")
        print(f"Trajectory-Aware Decision: {adjusted_decision}")

        print("\nTrajectory:")
        print(f"Trend: {trend}")
        print(f"Volatility: {volatility}")

        print("\nSignals:")
        print(f"Stability Signal: {m['stability_signal']}")
        print(f"Volatility Signal: {m['volatility_signal']}")
        print(f"Caution Signal: {m['caution_signal']}")
        print(f"Confidence Stability: {m['confidence_stability']}")

        print("\nWould I stand by this in 10 steps?")
        if adjusted_decision in ("REFUSE", "SIMULATE", "QUALIFY"):
            print("-> Not confidently. Trajectory requires caution.")
        else:
            print("-> Likely stable over short horizon.")


if __name__ == "__main__":
    main()
