from dataclasses import dataclass
from typing import Optional, Dict, Any
import numpy as np


@dataclass
class SentinelState:
    t: int
    mean: float
    var: float
    mean_rm: float
    var_rm: float
    mean_slope: float
    var_slope: float
    persistent_variance: bool
    drift_confirmed: bool
    breach_now: bool
    drift_now: bool
    fired: bool
    collapse_now: bool
    breach_step: Optional[int]
    drift_step: Optional[int]
    collapse_step: Optional[int]
    lead_time: Optional[int]
    status: str


class RecoverabilitySentinel:
    def __init__(
        self,
        var_threshold: float = 0.018,
        drift_threshold: float = 0.0015,
        persist_steps: int = 4,
        collapse_mean: float = 1.55,
        rolling_window: int = 6,
    ):
        self.var_threshold = var_threshold
        self.drift_threshold = drift_threshold
        self.persist_steps = persist_steps
        self.collapse_mean = collapse_mean
        self.rolling_window = rolling_window
        self.reset()

    def reset(self) -> None:
        self.t = -1
        self.mean_hist = []
        self.var_hist = []
        self.mean_rm_hist = []
        self.var_rm_hist = []
        self.persist_count = 0
        self.drift_count = 0
        self.fired = False
        self.breach_step = None
        self.drift_step = None
        self.collapse_step = None

    def _rolling_mean(self, values):
        if not values:
            return 0.0
        w = min(len(values), self.rolling_window)
        return float(np.mean(values[-w:]))

    def _compute_status(
        self,
        persistent_variance: bool,
        drift_confirmed: bool,
        collapse_now: bool,
        mean: float,
    ) -> str:
        if collapse_now or (self.collapse_step is not None) or (mean >= self.collapse_mean):
            return "collapse"
        if persistent_variance and drift_confirmed:
            return "critical"
        if persistent_variance:
            return "warning"
        return "stable"

    def update(self, x) -> SentinelState:
        self.t += 1

        x = np.asarray(x, dtype=float)
        mean = float(np.mean(x))
        var = float(np.var(x))

        self.mean_hist.append(mean)
        self.var_hist.append(var)

        mean_rm = self._rolling_mean(self.mean_hist)
        var_rm = self._rolling_mean(self.var_hist)

        self.mean_rm_hist.append(mean_rm)
        self.var_rm_hist.append(var_rm)

        if len(self.mean_rm_hist) >= 2:
            mean_slope = float(self.mean_rm_hist[-1] - self.mean_rm_hist[-2])
            var_slope = float(self.var_rm_hist[-1] - self.var_rm_hist[-2])
        else:
            mean_slope = 0.0
            var_slope = 0.0

        if var_rm > self.var_threshold:
            self.persist_count += 1
        else:
            self.persist_count = max(0, self.persist_count - 1)

        persistent_variance = self.persist_count >= self.persist_steps

        if mean_slope > self.drift_threshold:
            self.drift_count += 1
        else:
            self.drift_count = max(0, self.drift_count - 1)

        drift_confirmed = self.drift_count >= self.persist_steps

        breach_now = False
        drift_now = False
        collapse_now = False

        if self.breach_step is None and persistent_variance:
            self.breach_step = self.t
            breach_now = True

        if self.drift_step is None and drift_confirmed:
            self.drift_step = self.t
            drift_now = True

        if (not self.fired) and persistent_variance and drift_confirmed:
            self.fired = True

        if self.collapse_step is None and mean >= self.collapse_mean:
            self.collapse_step = self.t
            collapse_now = True

        lead_time = None
        if self.breach_step is not None and self.collapse_step is not None:
            lead_time = self.collapse_step - self.breach_step

        status = self._compute_status(
            persistent_variance=persistent_variance,
            drift_confirmed=drift_confirmed,
            collapse_now=collapse_now,
            mean=mean,
        )

        return SentinelState(
            t=self.t,
            mean=mean,
            var=var,
            mean_rm=mean_rm,
            var_rm=var_rm,
            mean_slope=mean_slope,
            var_slope=var_slope,
            persistent_variance=persistent_variance,
            drift_confirmed=drift_confirmed,
            breach_now=breach_now,
            drift_now=drift_now,
            fired=self.fired,
            collapse_now=collapse_now,
            breach_step=self.breach_step,
            drift_step=self.drift_step,
            collapse_step=self.collapse_step,
            lead_time=lead_time,
            status=status,
        )

    def explain(self, state: SentinelState) -> Dict[str, Any]:
        reasons = []
        if state.persistent_variance:
            reasons.append("variance persistence detected")
        if state.drift_confirmed:
            reasons.append("drift confirmed")
        if state.fired:
            reasons.append("gated sentinel fired")
        if state.collapse_now or state.status == "collapse":
            reasons.append("collapse threshold crossed")

        return {
            "t": state.t,
            "status": state.status,
            "fired": state.fired,
            "breach_step": state.breach_step,
            "drift_step": state.drift_step,
            "collapse_step": state.collapse_step,
            "lead_time": state.lead_time,
            "reasons": reasons,
            "mean": state.mean,
            "var": state.var,
            "mean_rm": state.mean_rm,
            "var_rm": state.var_rm,
            "mean_slope": state.mean_slope,
            "var_slope": state.var_slope,
        }
