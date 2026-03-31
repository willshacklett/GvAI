from gvai.real_gv import evaluate_real_gv
from gvai.agent import generate_action, generate_question


def main():
    result = evaluate_real_gv()
    summary = result["summary"]
    decision = result["decision"]

    action = generate_action(summary, decision)
    question = generate_question(summary, decision)

    print("\n=== GvAI Real GV ===")
    print(f"CSV Path: {result['path']}")
    print(f"Decision: {decision}")
    print(f"Response: {result['response']}")
    print(f"Action: {action}")
    print(f"{question}")

    print("\nSummary:")
    print(f"Latest GV: {summary['gv_score']}")
    print(f"Average GV (window): {summary['avg_gv']}")
    print(f"Delta GV: {summary['delta_gv']}")
    print(f"Trend: {summary['trend']}")
    print(f"Volatility: {summary['volatility']}")
    print(f"Recoverability: {summary['recoverability']}")
    print(f"Risk: {summary['risk']}")
    print(f"Recovery State: {summary['recovery_state']}")
    print(f"Recovery Strength: {summary['recovery_strength']}")
    print(f"Recovery Confidence: {summary['recovery_confidence']}")
    print(f"Timestamp: {summary['timestamp']}")
    print(f"Label: {summary['label']}")


if __name__ == "__main__":
    main()
