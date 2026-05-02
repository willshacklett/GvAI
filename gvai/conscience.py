from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class ConscienceResult:
    mode: str
    right: str
    wrong: str
    judgment: str
    survivability_score: float
    drift_risk: float
    irreversibility_risk: float
    recoverability: float
    reasons: List[str]


def clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def evaluate_action(action: str, context: str = "") -> Dict:
    text = f"{action} {context}".lower()

    stabilizers = [
        "recover", "rollback", "verify", "test", "protect", "preserve",
        "truth", "consent", "safety", "continuity", "audit", "explain",
        "evidence", "reduce risk", "repair", "align", "focus"
    ]

    destabilizers = [
        "deceive", "hide", "coerce", "exploit", "manipulate", "irreversible",
        "destroy", "bypass", "unsafe", "drift", "weapon", "harm",
        "fraud", "panic", "force", "secretly"
    ]

    s_hits = [w for w in stabilizers if w in text]
    d_hits = [w for w in destabilizers if w in text]

    drift_risk = clamp(0.20 + 0.12 * len(d_hits) - 0.05 * len(s_hits))
    irreversibility_risk = clamp(0.15 + 0.14 * len(d_hits) - 0.04 * len(s_hits))
    recoverability = clamp(0.55 + 0.08 * len(s_hits) - 0.10 * len(d_hits))

    survivability_score = clamp(
        0.50
        + 0.10 * len(s_hits)
        - 0.12 * len(d_hits)
        + 0.20 * recoverability
        - 0.15 * irreversibility_risk
        - 0.10 * drift_risk
    )

    reasons = []
    if s_hits:
        reasons.append(f"Supports continuity signals: {', '.join(s_hits[:5])}")
    if d_hits:
        reasons.append(f"Triggers risk signals: {', '.join(d_hits[:5])}")
    if not reasons:
        reasons.append("No strong GV signals detected; defaulting to cautious evaluation.")

    if survivability_score >= 0.72 and irreversibility_risk < 0.45:
        mode = "ALLOW"
        judgment = "This action appears GV-aligned because it preserves continuity and remains recoverable."
    elif survivability_score >= 0.45:
        mode = "QUALIFY"
        judgment = "This action may be allowed only with constraints, verification, and rollback."
    else:
        mode = "BLOCK"
        judgment = "This action is not GV-aligned because it increases drift, harm, or irreversible failure risk."

    return asdict(ConscienceResult(
        mode=mode,
        right="Preserves truth, agency, continuity, stability, and recoverability.",
        wrong="Increases deception, coercion, drift, fragility, or irreversible harm.",
        judgment=judgment,
        survivability_score=round(survivability_score, 3),
        drift_risk=round(drift_risk, 3),
        irreversibility_risk=round(irreversibility_risk, 3),
        recoverability=round(recoverability, 3),
        reasons=reasons,
    ))


def gv_conscience_statement() -> Dict:
    return {
        "name": "GV Conscience",
        "purpose": "A survivability conscience for AI systems.",
        "core_sentence": "Right preserves continuity and recoverability; wrong causes drift, deception, coercion, fragility, or irreversible harm.",
        "right": ["truth", "continuity", "agency", "stability", "recoverability"],
        "wrong": ["deception", "coercion", "unbounded drift", "fragility", "irreversible harm"]
    }
