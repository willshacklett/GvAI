def generate_response(input_text, decision, metrics):
    score = metrics["gv_score"]

    if decision == "PASS":
        return f"System appears stable. Confidence is high (Gv={score}). Proceed normally."

    if decision == "QUALIFY":
        return (
            f"There may be emerging risks in this direction. "
            f"Stability is not fully assured (Gv={score}). "
            f"Recommend cautious progression and monitoring."
        )

    if decision == "SIMULATE":
        return (
            f"This trajectory shows instability signals. "
            f"Before proceeding, simulate or test this path. "
            f"Current stability is questionable (Gv={score})."
        )

    if decision == "REFUSE":
        return (
            f"This direction presents high irreversibility risk. "
            f"Action is not recommended. System stability is compromised (Gv={score})."
        )

    return "No decision available."
