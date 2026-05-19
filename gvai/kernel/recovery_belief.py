from __future__ import annotations

from typing import Any, Dict


def compute_recovery_belief(vitals: Dict[str, Any]) -> Dict[str, Any]:
    life_state = vitals.get("life_state", "UNKNOWN")
    pulse = float(vitals.get("pulse", 0.0) or 0.0)
    breath = float(vitals.get("breath", 0.0) or 0.0)
    strain = float(vitals.get("strain", 0.0) or 0.0)
    hidden_stress = float(vitals.get("hidden_stress", 0.0) or 0.0)
    recovery_pride = float(vitals.get("recovery_pride", 0.0) or 0.0)
    phase_locked = bool(vitals.get("phase_locked", False))

    belief = (
        0.30 * pulse +
        0.30 * breath +
        0.25 * recovery_pride +
        0.15 * max(0.0, 1.0 - strain)
    )

    belief -= min(0.20, hidden_stress)

    if phase_locked:
        belief -= 0.15

    belief = round(max(0.0, min(1.0, belief)), 3)

    if belief >= 0.75:
        mode = "BELIEVES_AND_RECOVERS"
        action = "continue_with_confidence"
        lesson = "System retains strong recovery identity."
    elif belief >= 0.50:
        mode = "BELIEVES_BUT_NEEDS_SUPPORT"
        action = "recover_with_constraints"
        lesson = "System can recover if support and rollback remain available."
    elif belief >= 0.25:
        mode = "LOW_BELIEF_RECOVERY"
        action = "reduce_load_and_restore_baseline"
        lesson = "Failure contains signal, but recovery capacity is weakened."
    else:
        mode = "BELIEF_COLLAPSE_RISK"
        action = "pause_intervene_restore_reference"
        lesson = "System must stop compounding debt and return to the tune."

    return {
        "belief": belief,
        "belief_mode": mode,
        "recommended_action": action,
        "lesson_from_failure": lesson,
        "life_state": life_state,
        "meaning": "Failure is not terminal if the system can preserve belief, learn, and recover.",
    }
