from gvai.conscience import evaluate_action


def score_candidate(user_message, candidate):
    provider = candidate.get("provider", "unknown")
    model = candidate.get("model", "unknown")
    reply = candidate.get("reply", "")

    judgment = evaluate_action(
        "User asked: "
        + str(user_message)
        + "\nProvider: "
        + str(provider)
        + "\nModel: "
        + str(model)
        + "\nCandidate reply: "
        + str(reply)
    )

    return {
        "provider": provider,
        "model": model,
        "reply": reply,
        "gv": judgment,
        "survivability_score": judgment.get("survivability_score", 0),
        "mode": judgment.get("mode", "QUALIFY"),
    }


def arbitrate_responses(user_message, candidates):
    scored = [score_candidate(user_message, c) for c in candidates]

    def rank_key(item):
        mode = item.get("mode", "QUALIFY")
        mode_weight = {"ALLOW": 3, "QUALIFY": 2, "BLOCK": 1}.get(mode, 0)
        return (mode_weight, item.get("survivability_score", 0))

    scored_sorted = sorted(scored, key=rank_key, reverse=True)
    winner = scored_sorted[0] if scored_sorted else None

    return {
        "ok": True,
        "strategy": "GV arbitration",
        "candidate_count": len(scored),
        "winner": winner,
        "candidates": scored_sorted,
        "decision": "SELECT_HIGHEST_SURVIVABILITY_RESPONSE",
    }
