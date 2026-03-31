import sys
from gvai.core import GvCore

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m gvai.cli "your text here"")
        return

    text = sys.argv[1]

    gv = GvCore()
    result = gv.evaluate(text)

    print("
=== GvAI Evaluation ===")
    print(f"Input: {result['input']}")
    print(f"Gv Score: {result['metrics']['gv_score']}")
    print(f"Drift Risk: {result['metrics']['drift_risk']}")
    print(f"Irreversibility Risk: {result['metrics']['irreversibility_risk']}")
    print(f"Confidence Stability: {result['metrics']['confidence_stability']}")
    print(f"Decision: {result['decision']}")

    print("
Would I stand by this in 10 steps?")
    if result["metrics"]["gv_score"] < 0.75:
        print("→ Not confidently. Requires qualification or simulation.")
    else:
        print("→ Likely stable over short horizon.")

if __name__ == "__main__":
    main()
