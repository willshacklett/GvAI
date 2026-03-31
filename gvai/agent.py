def generate_action(summary, decision):
    trend = summary.get("trend")
    recovery_state = summary.get("recovery_state")
    risk = summary.get("risk")
    gv = summary.get("gv_score")

    if decision == "REFUSE":
        return (
            "Stop the current path. Revert to the safest reversible state, "
            "then identify the smallest possible change that can be tested safely."
        )

    if decision == "SIMULATE":
        return (
            "Do not commit fully yet. Run a bounded test or micro-simulation, "
            "and define the rollback condition before proceeding."
        )

    if decision == "QUALIFY":
        if recovery_state == "FRAGILE_RECOVERY":
            return (
                "Recovery has started but is still fragile. Keep safeguards in place "
                "and require another confirming improvement before relaxing controls."
            )
        if recovery_state == "STABILIZING":
            return (
                "The system is stabilizing but not trustworthy yet. Hold the line, "
                "avoid aggressive changes, and wait for stronger recovery confirmation."
            )
        if trend == "DEGRADING":
            return (
                "Trajectory is weakening. Reduce change velocity, add explicit checks, "
                "and define the next trigger that would force simulation or rollback."
            )
        if risk is not None and risk >= 0.50:
            return (
                "Risk is elevated. Continue only with tighter controls and a clearly defined "
                "fallback path."
            )
        return (
            "Proceed cautiously. Keep monitoring active and identify the first signal "
            "that would invalidate the current path."
        )

    if decision == "PASS":
        if gv is not None and gv >= 0.80:
            return (
                "System is operating in a healthy range. Continue normal operation, "
                "but keep lightweight monitoring to catch any drift early."
            )
        return (
            "System is acceptable, but not deeply safe. Continue with monitoring "
            "and avoid unnecessary destabilizing changes."
        )

    return "No action available."


def generate_question(summary, decision):
    trend = summary.get("trend")
    recovery_state = summary.get("recovery_state")

    if decision == "REFUSE":
        return "Question: What smaller, reversible alternative achieves the same goal?"

    if decision == "SIMULATE":
        return "Question: What is the safest test that would give signal without committing fully?"

    if decision == "QUALIFY":
        if recovery_state in ("FRAGILE_RECOVERY", "STABILIZING"):
            return "Question: What signal would prove this recovery is real rather than temporary?"
        if trend == "DEGRADING":
            return "Question: What is the earliest warning sign that this degradation is accelerating?"
        return "Question: Which assumption here is most likely to fail first?"

    if decision == "PASS":
        return "Question: What change would most likely push this system out of stability?"

    return "Question: What signal do we need next?"
