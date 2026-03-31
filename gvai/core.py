import random
import time

class GvCore:
    def __init__(self):
        self.history = []

    def compute_gv(self, text):
        base = random.uniform(0.6, 0.95)
        novelty = min(len(set(text.split())) / 20.0, 0.2)
        score = max(0.0, min(1.0, base - novelty))

        drift = self._compute_drift(score)

        return {
            "gv_score": round(score, 3),
            "drift_risk": drift,
            "irreversibility_risk": self._irreversibility(score),
            "confidence_stability": round(1.0 - abs(0.8 - score), 3)
        }

    def _compute_drift(self, score):
        if score < 0.7:
            return "HIGH"
        elif score < 0.82:
            return "MEDIUM"
        return "LOW"

    def _irreversibility(self, score):
        if score < 0.65:
            return "CRITICAL"
        elif score < 0.75:
            return "ELEVATED"
        return "LOW"

    def decide(self, gv_metrics):
        score = gv_metrics["gv_score"]
        drift = gv_metrics["drift_risk"]

        if score < 0.65:
            return "REFUSE"
        elif drift == "HIGH":
            return "SIMULATE"
        elif drift == "MEDIUM":
            return "QUALIFY"
        return "PASS"

    def evaluate(self, text):
        metrics = self.compute_gv(text)
        decision = self.decide(metrics)

        result = {
            "input": text,
            "metrics": metrics,
            "decision": decision,
            "timestamp": time.time()
        }

        self.history.append(result)
        return result
