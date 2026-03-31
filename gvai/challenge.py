def generate_challenge(input_text, decision, metrics, trend, volatility):
    gv = metrics["gv_score"]

    # Only challenge when things are drifting or unstable
    if decision == "PASS" and trend != "DEGRADING":
        return None

    if decision == "QUALIFY":
        return (
            "Question: What specific risk are you trying to address, and is there a reversible way to test it first?"
        )

    if decision == "SIMULATE":
        return (
            "Question: What happens if this approach fails? Do you have a recovery path, or are you committing fully?"
        )

    if decision == "REFUSE":
        return (
            "Challenge: This path removes recovery options. Why is a non-reversible approach necessary here?"
        )

    return None
