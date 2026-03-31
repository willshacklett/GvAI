import json
import os
from gvai.real_gv import evaluate_real_gv, find_csv_path, read_rows, latest_window
from gvai.agent import generate_action, generate_question


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


def build_payload():
    result = evaluate_real_gv()
    summary = result["summary"]
    decision = result["decision"]

    action = generate_action(summary, decision)
    question = generate_question(summary, decision)

    history = []
    csv_path = result["path"] or find_csv_path()
    if csv_path:
        rows = read_rows(csv_path)
        window_rows = latest_window(rows, window=8)
        history = [
            {
                "timestamp": r.get("timestamp"),
                "label": r.get("label"),
                "gv_score": r.get("gv_score"),
                "recoverability": r.get("recoverability"),
                "risk": r.get("risk"),
            }
            for r in window_rows
        ]

    return {
        "decision": decision,
        "severity": severity(decision),
        "response": result["response"],
        "action": action,
        "question": question,
        "summary": summary,
        "history": history,
    }


def export_state():
    payload = build_payload()
    os.makedirs("dashboard", exist_ok=True)
    with open("dashboard/gvai_state.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def main():
    export_state()
    print("Exported dashboard/gvai_state.json")


if __name__ == "__main__":
    main()
