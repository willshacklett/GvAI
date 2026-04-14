# (I'll shorten slightly for stability — same logic, less risk)

class GvIdentity:
    def __init__(self):
        self.canonical_gv = 1.0
        self.history = []

    def start_new_conversation(self):
        self.history = []
        return self.canonical_gv

    def update(self, prev_gv, drift, contradiction, coherence, volatility):
        recoverability = max(0.0, 1.0 - drift * 1.5)

        penalty = (
            0.40 * drift +
            0.25 * contradiction +
            0.15 * (1.0 - coherence) +
            0.12 * volatility
        )

        bonus = 0.10 * recoverability if prev_gv > 0.65 else 0.0
        stability_pull = 0.05 * (1.0 - prev_gv)

        new_gv = prev_gv - penalty + bonus + stability_pull
        new_gv = max(0.0, min(1.0, new_gv))

        self.history.append(new_gv)
        return new_gv
