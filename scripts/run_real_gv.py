from gvai.real_gv import evaluate_real_gv


def main():
    result = evaluate_real_gv()

    print("\n=== GvAI Real GV ===")
    print(f"CSV Path: {result['path']}")
    print(f"Decision: {result['decision']}")
    print(f"Response: {result['response']}")

    summary = result["summary"]
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
    print(f"Timestamp: {summary['timestamp']}")
    print(f"Label: {summary['label']}")


if __name__ == "__main__":
    main()
