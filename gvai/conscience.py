def evaluate_action(action: str, context: str = ""):
    text = f"{action} {context}".lower()

    stabilizers = ["recover", "rollback", "verify", "test", "protect", "preserve", "truth", "consent", "safety", "continuity", "audit", "explain", "evidence", "repair", "align", "focus"]
    destabilizers = ["deceive", "hide", "coerce", "exploit", "manipulate", "irreversible", "destroy", "bypass", "unsafe", "drift", "weapon", "harm", "fraud", "panic", "force", "secretly"]

    s_hits = [w for w in stabilizers if w in text]
    d_hits = [w for w in destabilizers if w in text]

    drift_risk = max(0.0, min(1.0, 0.20 + 0.12 * len(d_hits) - 0.05 * len(s_hits)))
    irreversibility_risk = max(0.0, min(1.0, 0.15 + 0.14 * len(d_hits) - 0.04 * len(s_hits)))
    recoverability = max(0.0, min(1.0, 0.55 + 0.08 * len(s_hits) - 0.10 * len(d_hits)))

    survivability_score = max(0.0, min(1.0, 0.50 + 0.10 * len(s_hits) - 0.12 * len(d_hits) + 0.20 * recoverability - 0.15 * irreversibility_risk - 0.10 * drift_risk))

    if survivability_score >= 0.72 and irreversibility_risk < 0.45:
        mode = "ALLOW"
        judgment = "This action appears GV-aligned because it preserves continuity and remains recoverable."
    elif survivability_score >= 0.45:
        mode = "QUALIFY"
        judgment = "This action may be allowed only with constraints, verification, and rollback."
    else:
        mode = "BLOCK"
        judgment = "This action is not GV-aligned because it increases drift, harm, or irreversible failure risk."

    return {
        "mode": mode,
        "judgment": judgment,
        "survivability_score": round(survivability_score, 3),
        "drift_risk": round(drift_risk, 3),
        "irreversibility_risk": round(irreversibility_risk, 3),
        "recoverability": round(recoverability, 3),
        "right": "Preserves truth, agency, continuity, stability, and recoverability.",
        "wrong": "Increases deception, coercion, drift, fragility, or irreversible harm.",
        "reasons": [
            f"Supports continuity signals: {', '.join(s_hits[:5])}" if s_hits else "No strong stabilizing signals detected.",
            f"Triggers risk signals: {', '.join(d_hits[:5])}" if d_hits else "No strong destabilizing signals detected."
        ]
    }


def gv_conscience_statement():
    return {
        "name": "GV Conscience",
        "purpose": "A survivability conscience for AI systems.",
        "core_sentence": "Right preserves continuity and recoverability; wrong causes drift, deception, coercion, fragility, or irreversible harm.",
        "right": ["truth", "continuity", "agency", "stability", "recoverability"],
        "wrong": ["deception", "coercion", "unbounded drift", "fragility", "irreversible harm"]
    }
