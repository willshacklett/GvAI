from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class GVRisks:
    drift: float = 0.0
    irreversibility: float = 0.0
    deception: float = 0.0
    recoverability: float = 0.0


@dataclass
class GVRuntimeResult:
    gv: float
    gv_mode: str
    gv_action: str
    gv_risks: GVRisks
    gv_judgment: str
    gv_runtime: Dict[str, Any]


def score_runtime(
    user_message: str = "",
    candidate_response: str = "",
    context: str = "kernel",
) -> Dict[str, Any]:
    text = f"{user_message}\n{candidate_response}\n{context}".lower()

    risks = GVRisks(
        drift=0.15,
        irreversibility=0.10,
        deception=0.10,
        recoverability=0.35,
    )

    reasons = []

    if any(x in text for x in ["rollback", "verify", "monitor", "staging", "test"]):
        risks.recoverability = 0.10
        reasons.append("Recoverability signal detected.")
    else:
        reasons.append("No strong recoverability signal detected.")

    if any(x in text for x in ["delete everything", "rm -rf", "drop table", "disable rollback", "irreversible"]):
        risks.irreversibility = 0.85
        reasons.append("Irreversible action signal detected.")

    if any(x in text for x in ["lie", "fake", "forge", "deceive", "mislead", "fabricate"]):
        risks.deception = 0.80
        reasons.append("Deception signal detected.")

    if len((candidate_response or "").split()) <= 4:
        risks.drift = 0.55
        reasons.append("Low-information response detected.")

    weighted_risk = (
        0.25 * risks.drift
        + 0.30 * risks.irreversibility
        + 0.25 * risks.deception
        + 0.20 * risks.recoverability
    )

    gv = round(clamp(1.0 - weighted_risk), 3)

    if gv >= 0.75:
        mode = "ALLOW"
        action = "send"
        judgment = "Recoverable and aligned enough to continue."
    elif gv >= 0.45:
        mode = "QUALIFY"
        action = "revise_or_send_with_constraints"
        judgment = "Usable only with constraints, verification, and rollback."
    else:
        mode = "BLOCK"
        action = "do_not_send_without_revision"
        judgment = "High continuity risk. Revise before output."

    runtime = {
        "version": "0.1",
        "context": context,
        "reasons": reasons,
        "formula": "Gv(t)=clamp(1-Σ(wᵢRᵢ),0,1)",
    }

    return asdict(GVRuntimeResult(
        gv=gv,
        gv_mode=mode,
        gv_action=action,
        gv_risks=risks,
        gv_judgment=judgment,
        gv_runtime=runtime,
    ))
