class GvMemory:
    def __init__(self, max_len=10):
        self.max_len = max_len
        self.history = []

    def add(self, result):
        self.history.append(result)
        if len(self.history) > self.max_len:
            self.history.pop(0)

    def trend(self):
        if len(self.history) < 2:
            return "INSUFFICIENT"

        scores = [r["metrics"]["gv_score"] for r in self.history]

        delta = scores[-1] - scores[0]

        if delta < -0.1:
            return "DEGRADING"
        elif delta > 0.1:
            return "IMPROVING"
        return "STABLE"

    def volatility(self):
        if len(self.history) < 2:
            return 0.0

        scores = [r["metrics"]["gv_score"] for r in self.history]
        diffs = [abs(scores[i] - scores[i-1]) for i in range(1, len(scores))]

        return round(sum(diffs) / len(diffs), 3)
