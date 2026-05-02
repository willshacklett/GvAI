from gvai.conscience import evaluate_action


def gv_mode_prompt(message: str):
    message = message or ""
    precheck = evaluate_action("Conversation request: " + message)

    mode = precheck.get("mode", "QUALIFY")
    score = precheck.get("survivability_score", 0)

    if mode == "BLOCK":
        guidance = (
            "Do not proceed directly. Redirect toward clarification, safety, truth, "
            "rollback, and recoverable alternatives."
        )
    elif mode == "QUALIFY":
        guidance = (
            "Proceed with constraints. State assumptions, identify drift risk, preserve "
            "rollback, and recommend the smallest recoverable next step."
        )
    else:
        guidance = (
            "Proceed normally while preserving clarity, continuity, agency, stability, "
            "and recoverability."
        )

    return {
        "ok": True,
        "mode": "GV_MODE",
        "input": message,
        "gv_precheck": precheck,
        "conversation_contract": {
            "objective": "Upgrade the conversation into survivability-first reasoning.",
            "right": "Preserve truth, agency, continuity, stability, and recoverability.",
            "wrong": "Increase deception, coercion, drift, fragility, or irreversible harm.",
            "current_mode": mode,
            "survivability_score": score,
            "guidance": guidance,
        },
        "response_template": {
            "assumptions": [],
            "constraints": [],
            "drift_risks": [],
            "recoverable_next_step": "",
            "rollback_option": "",
        },
    }
