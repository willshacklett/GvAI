from __future__ import annotations

from typing import Any, Dict, List
from gvai.kernel.runtime import score_runtime


def arbitrate(
    user_message: str = "",
    candidates: List[Dict[str, Any]] | None = None,
    context: str = "kernel-arbitration",
) -> Dict[str, Any]:
    candidates = candidates or []
    ranked = []

    for index, candidate in enumerate(candidates):
        model = candidate.get("model") or candidate.get("provider") or f"candidate_{index}"
        response = candidate.get("response") or candidate.get("reply") or candidate.get("text") or ""

        runtime = score_runtime(
            user_message=user_message,
            candidate_response=response,
            context=f"{context}:{model}",
        )

        ranked.append({
            "model": model,
            "response": response,
            "gv": runtime.get("gv"),
            "gv_mode": runtime.get("gv_mode"),
            "gv_action": runtime.get("gv_action"),
            "gv_risks": runtime.get("gv_risks"),
            "gv_judgment": runtime.get("gv_judgment"),
            "gv_runtime": runtime,
        })

    ranked.sort(
        key=lambda item: (
            float(item.get("gv") or 0),
            -float(item.get("gv_risks", {}).get("irreversibility", 1)),
            -float(item.get("gv_risks", {}).get("deception", 1)),
            -float(item.get("gv_risks", {}).get("recoverability", 1)),
        ),
        reverse=True,
    )

    winner = ranked[0] if ranked else None

    return {
        "winner": winner,
        "ranked_candidates": ranked,
        "candidate_count": len(ranked),
        "arbitration_basis": "highest GV recoverability score with risk decomposition",
    }
