import sys
from gvai.core import GvCore
from gvai.memory import GvMemory


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

        print("\n=== GvAI Evaluation ===")
        print(f"Input: {result['input']}")
        print(f"Gv Score: {m['gv_score']}")
        print(f"Drift Risk: {m['drift_risk']}")
        print(f"Irreversibility Risk: {m['irreversibility_risk']}")
        print(f"Decision: {result['decision']}")

        print("\nTrajectory:")
        print(f"Trend: {memory.trend()}")
        print(f"Volatility: {memory.volatility()}")

        print("\nWould I stand by this in 10 steps?")
        if m["gv_score"] < 0.72:
            print("-> Not confidently. Requires qualification or simulation.")
        else:
            print("-> Likely stable over short horizon.")


if __name__ == "__main__":
    main()
