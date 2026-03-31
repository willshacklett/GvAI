import os
import time
from gvai.real_gv import evaluate_real_gv


def severity(decision):
    if decision == "REFUSE":
        return "CRITICAL"
    if decision == "SIMULATE":
        return "HIGH"
    if decision == "QUALIFY":
        return "MEDIUM"
    if decision == "PASS":
        return "INFO"
    return "UNKNOWN"


def alert_reasons(current, previous):
    reasons = []

    csum = current["summary"]
    psum = previous["summary"] if previous else None

    c_decision = current["decision"]
    p_decision = previous["decision"] if previous else None

    c_gv = csum.get("gv_score")
    p_gv = psum.get("gv_score") if psum else None

    c_trend = csum.get("trend")
    p_trend = psum.get("trend") if psum else None

    c_risk = csum.get("risk")
    p_risk = psum.get("risk") if psum else None

    c_recovery_state = csum.get("recovery_state")
    p_recovery_state = psum.get("recovery_state") if psum else None

    if previous is None:
        reasons.append("initial_state")
        return reasons

    if c_decision != p_decision:
        reasons.append(f"decision_changed:{p_decision}->{c_decision}")

    if c_trend == "DEGRADING" and p_trend != "DEGRADING":
        reasons.append("trend_became_degrading")

    if c_trend == "IMPROVING" and p_trend != "IMPROVING":
        reasons.append("trend_became_improving")

    if c_recovery_state != p_recovery_state and c_recovery_state in ("FRAGILE_RECOVERY", "STABILIZING", "STABLE_RECOVERY"):
        reasons.append(f"recovery_state:{p_recovery_state}->{c_recovery_state}")

    if c_gv is not None and p_gv is not None:
        drop = p_gv - c_gv
        if drop >= 0.05:
            reasons.append(f"gv_drop:{drop:.3f}")

    if c_risk is not None:
        if p_risk is None and c_risk >= 0.50:
            reasons.append(f"risk_high:{c_risk:.3f}")
        elif p_risk is not None and p_risk < 0.50 <= c_risk:
            reasons.append(f"risk_crossed_0.50:{p_risk:.3f}->{c_risk:.3f}")

    if c_decision in ("REFUSE", "SIMULATE") and p_decision != c_decision:
        reasons.append("action_required")

    return reasons


def should_alert(current, previous):
    reasons = alert_reasons(current, previous)
    meaningful = [r for r in reasons if r != "initial_state"]
    return (len(meaningful) > 0), reasons


def print_alert(current, reasons):
    summary = current["summary"]
    sev = severity(current["decision"])

    print("=== GvAI ALERT ===")
    print(f"Severity: {sev}")
    print(f"Decision: {current['decision']}")
    print(f"Reasons: {', '.join(reasons)}")
    print(f"Response: {current['response']}")
    print("Summary:")
    print(f"  Latest GV: {summary['gv_score']}")
    print(f"  Avg GV: {summary['avg_gv']}")
    print(f"  Delta GV: {summary['delta_gv']}")
    print(f"  Trend: {summary['trend']}")
    print(f"  Volatility: {summary['volatility']}")
    print(f"  Recoverability: {summary['recoverability']}")
    print(f"  Risk: {summary['risk']}")
    print(f"  Recovery State: {summary['recovery_state']}")
    print(f"  Recovery Strength: {summary['recovery_strength']}")
    print(f"  Recovery Confidence: {summary['recovery_confidence']}")
    print(f"  Timestamp: {summary['timestamp']}")
    print(f"  Label: {summary['label']}")
    print()


def print_baseline(current):
    summary = current["summary"]
    print("=== GvAI Monitor Baseline ===")
    print(f"Decision: {current['decision']}")
    print(f"Response: {current['response']}")
    print("Summary:")
    print(f"  Latest GV: {summary['gv_score']}")
    print(f"  Trend: {summary['trend']}")
    print(f"  Volatility: {summary['volatility']}")
    print(f"  Risk: {summary['risk']}")
    print(f"  Recovery State: {summary['recovery_state']}")
    print(f"  Recovery Strength: {summary['recovery_strength']}")
    print(f"  Recovery Confidence: {summary['recovery_confidence']}")
    print(f"  Timestamp: {summary['timestamp']}")
    print(f"  Label: {summary['label']}")
    print()


def main():
    interval = float(os.getenv("GVAI_MONITOR_INTERVAL", "10"))
    print(f"GvAI Real GV Alert Monitor running (interval={interval}s). Press Ctrl+C to stop.\n")

    previous = None
    first = True

    try:
        while True:
            current = evaluate_real_gv()

            if first:
                print_baseline(current)
                first = False
            else:
                fire, reasons = should_alert(current, previous)
                if fire:
                    print_alert(current, reasons)

            previous = current
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nAlert monitor stopped.")


if __name__ == "__main__":
    main()
