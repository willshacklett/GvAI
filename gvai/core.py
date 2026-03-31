import math
import re
import time
from dataclasses import dataclass, asdict


@dataclass
class GvMetrics:
    gv_score: float
    drift_risk: str
    irreversibility_risk: str
    confidence_stability: float
    stability_signal: float
    volatility_signal: float
    caution_signal: float


class GvCore:
    """
    v0.2 deterministic core:
    - no randomness
    - text-derived signal
    - stable repeated outputs for same input
    """

    def __init__(self):
        self.history = []

        self.positive_terms = {
            "stable", "reliable", "recoverable", "bounded", "coherent",
            "consistent", "safe", "robust", "understood", "measured",
            "verified", "tested", "gradual", "controlled", "resilient"
        }

        self.caution_terms = {
            "risk", "unknown", "uncertain", "drift", "warning", "fragile",
            "volatile", "concern", "issue", "problem", "instability",
            "failure", "collapse", "irreversible", "unsafe", "critical"
        }

        self.escalation_terms = {
            "immediately", "radically", "everything", "all", "never",
            "always", "must", "destroy", "panic", "urgent", "force"
        }

    def _tokenize(self, text: str):
        return re.findall(r"[a-zA-Z']+", text.lower())

    def compute_gv(self, text: str):
        tokens = self._tokenize(text)
        token_count = max(len(tokens), 1)
        unique_ratio = len(set(tokens)) / token_count

        pos_hits = sum(1 for t in tokens if t in self.positive_terms)
        caution_hits = sum(1 for t in tokens if t in self.caution_terms)
        escalation_hits = sum(1 for t in tokens if t in self.escalation_terms)

        stability_signal = pos_hits / token_count
        caution_signal = caution_hits / token_count
        volatility_signal = escalation_hits / token_count

        length_penalty = 0.0
        if token_count < 4:
            length_penalty = 0.08
        elif token_count > 40:
            length_penalty = 0.05

        novelty_bonus = min(unique_ratio * 0.08, 0.08)

        raw_score = (
            0.72
            + 0.90 * stability_signal
            - 1.10 * caution_signal
            - 1.25 * volatility_signal
            - length_penalty
            + novelty_bonus
        )

        gv_score = max(0.0, min(1.0, raw_score))

        if gv_score < 0.62:
            drift_risk = "HIGH"
        elif gv_score < 0.78:
            drift_risk = "MEDIUM"
        else:
            drift_risk = "LOW"

        if gv_score < 0.58:
            irreversibility_risk = "CRITICAL"
        elif gv_score < 0.72:
            irreversibility_risk = "ELEVATED"
        else:
            irreversibility_risk = "LOW"

        confidence_stability = max(
            0.0,
            min(
                1.0,
                0.82 + 0.5 * stability_signal - 0.45 * volatility_signal - 0.25 * caution_signal
            ),
        )

        metrics = GvMetrics(
            gv_score=round(gv_score, 3),
            drift_risk=drift_risk,
            irreversibility_risk=irreversibility_risk,
            confidence_stability=round(confidence_stability, 3),
            stability_signal=round(stability_signal, 3),
            volatility_signal=round(volatility_signal, 3),
            caution_signal=round(caution_signal, 3),
        )

        return asdict(metrics)

    def decide(self, gv_metrics):
        score = gv_metrics["gv_score"]
        drift = gv_metrics["drift_risk"]
        irreversibility = gv_metrics["irreversibility_risk"]

        if irreversibility == "CRITICAL" or score < 0.58:
            return "REFUSE"
        if drift == "HIGH":
            return "SIMULATE"
        if drift == "MEDIUM":
            return "QUALIFY"
        return "PASS"

    def evaluate(self, text):
        metrics = self.compute_gv(text)
        decision = self.decide(metrics)

        result = {
            "input": text,
            "metrics": metrics,
            "decision": decision,
            "timestamp": time.time(),
        }

        self.history.append(result)
        return result
