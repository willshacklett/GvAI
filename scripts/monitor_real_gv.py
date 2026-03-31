import os
import time
from gvai.real_gv import evaluate_real_gv


def fingerprint(result):
    summary = result["summary"]
    return (
        result["decision"],
        summary.get("gv_score"),
        summary.get("trend"),
        summary.get("volatility"),
        summary.get("timestamp"),
        summary.get("label"),
    )


def main():
    interval = float(os.getenv("GVAI_MONITOR_INTERVAL", "10"))
    print(f"GvAI Real GV Monitor running (interval={interval}s). Press Ctrl+C to stop.\n")

    last_fp = None

    try:
        while True:
            result = evaluate_real_gv()
            fp = fingerprint(result)
            summary = result["summary"]

            if fp != last_fp:
                print("=== GvAI Monitor Update ===")
                print(f"CSV Path: {result['path']}")
                print(f"Decision: {result['decision']}")
                print(f"Response: {result['response']}")
                print("Summary:")
                print(f"  Latest GV: {summary['gv_score']}")
                print(f"  Avg GV: {summary['avg_gv']}")
                print(f"  Delta GV: {summary['delta_gv']}")
                print(f"  Trend: {summary['trend']}")
                print(f"  Volatility: {summary['volatility']}")
                print(f"  Recoverability: {summary['recoverability']}")
                print(f"  Risk: {summary['risk']}")
                print(f"  Timestamp: {summary['timestamp']}")
                print(f"  Label: {summary['label']}")
                print()
                last_fp = fp

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
