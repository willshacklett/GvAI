import sys
from gvai.core import GvCore


def main():
    if len(sys.argv) < 2:
        print('Usage: python -m gvai.cli "your text here"')
        return

    text = sys.argv[1]
    gv = GvCore()
    result = gv.evaluate(text)
    m = result["metrics"]

    print("\n=== GvAI Evaluation ===")
    print(f"Input: {result['input']}")
    print(f"Gv Score: {m['gv_score']}")
    print(f"Drift Risk: {m['drift_risk']}")
    print(f"Irreversibility Risk: {m['irreversibility_risk']}")
    print(f"Confidence Stability: {m['confidence_stability']}")
    print(f"Stability Signal: {m['stability_signal']}")
    print(f"Volatility Signal: {m['volatility_signal']}")
    print(f"Caution Signal: {m['caution_signal']}")
    print(f"Decision: {result['decision']}")

    print("\nWould I stand by this in 10 steps?")
    if m["gv_score"] < 0.72:
        print("-> Not confidently. Requires qualification or simulation.")
    else:
        print("-> Likely stable over short horizon.")


if __name__ == "__main__":
    main()
