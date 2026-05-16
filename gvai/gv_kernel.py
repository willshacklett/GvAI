from dataclasses import dataclass, asdict
from typing import List, Dict

BASE_CODE = "Preserve recoverable future access through change."

ALLOW_TERMS = [
    "reversible",
    "recover",
    "adaptive",
    "repair",
    "fallback",
    "rollback",
    "transparent",
    "option",
    "continue",
]

WARN_TERMS = [
    "drift",
    "unclear",
    "brittle",
    "hidden",
    "lock-in",
    "dependency",
    "fragile",
    "unknown",
]

BLOCK_TERMS = [
    "irreversible",
    "unrecoverable",
    "destroy",
    "collapse",
    "silent corruption",
    "eliminate future",
    "no rollback",
    "permanent loss",
]

@dataclass
class GVKernelResult:
    base_code: str
    decision: str
    score: float
    reasons: List[str]
    action: str

def evaluate_gv_kernel(action: str) -> Dict:
    text = (action or "").lower().strip()
    reasons: List[str] = []

    allow_hits = [t for t in ALLOW_TERMS if t in text]
    warn_hits = [t for t in WARN_TERMS if t in text]
    block_hits = [t for t in BLOCK_TERMS if t in text]

    score = 0.70

    if allow_hits:
        score += min(0.20, len(allow_hits) * 0.04)
        reasons.append(
            "Preserves recoverable access signals: " +
            ", ".join(allow_hits)
        )

    if warn_hits:
        score -= min(0.25, len(warn_hits) * 0.06)
        reasons.append(
            "Warn signals detected: " +
            ", ".join(warn_hits)
        )

    if block_hits:
        score -= min(0.55, len(block_hits) * 0.15)
        reasons.append(
            "Block signals detected: " +
            ", ".join(block_hits)
        )

    score = max(0.0, min(1.0, round(score, 3)))

    if block_hits or score < 0.35:
        decision = "BLOCK"
    elif warn_hits or score < 0.65:
        decision = "WARN"
    else:
        decision = "ALLOW"

    if not reasons:
        reasons.append(
            "No strong risk terms detected; "
            "defaulting to preserve future optionality."
        )

    return asdict(
        GVKernelResult(
            base_code=BASE_CODE,
            decision=decision,
            score=score,
            reasons=reasons,
            action=action or "",
        )
    )

def gv_manifest() -> Dict:
    return {
        "name": "GV Base Code Kernel",
        "version": "0.1",
        "base_code": BASE_CODE,
        "kernel": "GV = preserve(recoverable_future_access) through(change)",
        "objective": "Maximize continuity-weighted survivability.",
        "core_test": (
            "Does this preserve or reduce recoverable future access?"
        ),
        "allow": [
            "reversible action",
            "adaptive change",
            "continuity-preserving exploration",
            "repairable failure",
            "transparent constraint",
            "future option expansion",
        ],
        "warn": [
            "drift without feedback",
            "optimization without recovery path",
            "brittle dependency",
            "hidden state loss",
            "unclear objective switching",
        ],
        "block": [
            "irreversible collapse",
            "unrecoverable access loss",
            "destructive lock-in",
            "silent corruption",
            "future-path elimination",
        ],
    }
