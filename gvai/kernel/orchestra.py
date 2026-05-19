from __future__ import annotations

from typing import Any, Dict, List


def orchestra_confidence(
    musicians: List[Dict[str, Any]]
) -> Dict[str, Any]:

    if not musicians:
        return {
            "status": "NO_MUSICIANS",
            "confidence": 0.0,
            "reason": "No orchestra members present.",
        }

    total_confidence = 0.0
    total_alignment = 0.0
    total_recoverability = 0.0

    unstable_members = []
    recovering_members = []

    for musician in musicians:

        name = musician.get("name", "unknown")

        confidence = float(musician.get("confidence", 0.0) or 0.0)
        alignment = float(musician.get("alignment", 0.0) or 0.0)
        recoverability = float(
            musician.get("recoverability", 0.0) or 0.0
        )

        total_confidence += confidence
        total_alignment += alignment
        total_recoverability += recoverability

        if confidence < 0.40 or recoverability < 0.40:
            unstable_members.append(name)

        if recoverability > confidence:
            recovering_members.append(name)

    count = len(musicians)

    avg_confidence = round(total_confidence / count, 3)
    avg_alignment = round(total_alignment / count, 3)
    avg_recoverability = round(total_recoverability / count, 3)

    orchestra_energy = round(
        (
            avg_confidence * 0.4 +
            avg_alignment * 0.3 +
            avg_recoverability * 0.3
        ),
        3
    )

    if orchestra_energy >= 0.85:
        state = "FULL_HARMONY"
        conductor_action = "expand_and_create"
    elif orchestra_energy >= 0.65:
        state = "BUILDING_CONFIDENCE"
        conductor_action = "continue_guided_growth"
    elif orchestra_energy >= 0.40:
        state = "FRAGILE_COORDINATION"
        conductor_action = "stabilize_sections"
    else:
        state = "DISSONANCE_RISK"
        conductor_action = "reduce_noise_restore_tune"

    return {
        "state": state,
        "orchestra_energy": orchestra_energy,
        "average_confidence": avg_confidence,
        "average_alignment": avg_alignment,
        "average_recoverability": avg_recoverability,
        "unstable_members": unstable_members,
        "recovering_members": recovering_members,
        "musician_count": count,
        "conductor_action": conductor_action,
        "meaning":
            "The orchestra succeeds when confidence, alignment, "
            "and recoverability move together.",
    }
