def explain_reasoning(input_text, decision, metrics, trend, volatility):
    gv = metrics["gv_score"]
    drift = metrics["drift_risk"]
    irreversibility = metrics["irreversibility_risk"]
    stability = metrics.get("stability_signal", 0.0)
    caution = metrics.get("caution_signal", 0.0)
    vol_signal = metrics.get("volatility_signal", 0.0)

    if decision == "PASS":
        return (
            f"This input stays within a stable operating corridor. "
            f"Gv remains strong at {gv}, drift is {drift.lower()}, and no major irreversible pressure is visible. "
            f"The current direction appears recoverable and controlled."
        )

    if decision == "QUALIFY":
        return (
            f"This input is not failing outright, but it weakens trajectory quality. "
            f"Gv is {gv}, trend is {trend.lower()}, and caution is building without full collapse. "
            f"That means the system can continue, but it should do so with tighter monitoring and explicit checks."
        )

    if decision == "SIMULATE":
        return (
            f"This direction shows material instability pressure. "
            f"Gv is {gv}, drift is {drift.lower()}, volatility is {volatility}, and recovery confidence is weakening. "
            f"The safer move is to test or simulate before committing to action."
        )

    if decision == "REFUSE":
        return (
            f"This path crosses into unacceptable territory. "
            f"Gv is {gv}, irreversibility risk is {irreversibility.lower()}, and the trajectory is degrading with volatility {volatility}. "
            f"Continuing would reduce recovery paths rather than preserve them."
        )

    return "No reasoning available."


def propose_next_step(input_text, decision):
    if decision == "PASS":
        return "Recommended next step: proceed normally, but keep lightweight monitoring in place."

    if decision == "QUALIFY":
        return "Recommended next step: continue cautiously, add explicit checks, and watch for further degradation."

    if decision == "SIMULATE":
        return "Recommended next step: run a bounded test, micro-simulation, or staged rollout before proceeding."

    if decision == "REFUSE":
        return "Recommended next step: stop this path and replace it with an incremental, reversible alternative."

    return "Recommended next step: gather more signal."


def generate_brain_response(input_text, decision, metrics, trend, volatility):
    reasoning = explain_reasoning(input_text, decision, metrics, trend, volatility)
    next_step = propose_next_step(input_text, decision)

    return f"{reasoning} {next_step}"
