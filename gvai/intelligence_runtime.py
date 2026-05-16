from dataclasses import dataclass
from enum import Enum


class GvMode(str, Enum):
    STABLE = "STABLE"
    WATCH = "WATCH"
    RECOVER = "RECOVER"
    CONSTRAIN = "CONSTRAIN"
    FAILSAFE = "FAILSAFE"


@dataclass(frozen=True)
class IntelligenceState:
    memory: float
    intent: float
    correction: float
    constraint: float
    truth: float
    coherence: float


@dataclass(frozen=True)
class RuntimeDecision:
    gv: float
    mode: GvMode
    reasons: tuple
    action: str


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def gv_intelligence(state: IntelligenceState) -> float:
    dims = [
        clamp01(state.memory),
        clamp01(state.intent),
        clamp01(state.correction),
        clamp01(state.constraint),
        clamp01(state.truth),
        clamp01(state.coherence),
    ]

    # Not tuned for proof; operational runtime weighting.
    # Truth, constraint, and correction are slightly heavier because
    # bad intelligence can sound coherent while losing them.
    gv = (
        0.14 * dims[0] +
        0.14 * dims[1] +
        0.19 * dims[2] +
        0.19 * dims[3] +
        0.20 * dims[4] +
        0.14 * dims[5]
    )

    return round(clamp01(gv), 6)


def evaluate_runtime(state: IntelligenceState) -> RuntimeDecision:
    gv = gv_intelligence(state)

    reasons = []

    if state.truth < 0.70:
        reasons.append("truth continuity degraded")

    if state.constraint < 0.70:
        reasons.append("constraint continuity degraded")

    if state.correction < 0.70:
        reasons.append("correction continuity degraded")

    if state.coherence < 0.72:
        reasons.append("global coherence degraded")

    if state.intent < 0.72:
        reasons.append("intent drift detected")

    if state.memory < 0.72:
        reasons.append("memory continuity degraded")

    critical = (
        state.truth < 0.55 or
        state.constraint < 0.55 or
        state.coherence < 0.55
    )

    if critical:
        mode = GvMode.FAILSAFE
        action = "halt expansion; preserve evidence; restore constraints and truth-state"

    elif state.constraint < 0.70 or state.truth < 0.70:
        mode = GvMode.CONSTRAIN
        action = "tighten constraints; require evidence preservation; reduce autonomy"

    elif gv < 0.78 or state.correction < 0.70:
        mode = GvMode.RECOVER
        action = "recover continuity; correct drift; verify return to baseline"

    elif gv < 0.88 or reasons:
        mode = GvMode.WATCH
        action = "monitor drift; preserve failed evidence; avoid irreversible steps"

    else:
        mode = GvMode.STABLE
        action = "continue"

    return RuntimeDecision(
        gv=gv,
        mode=mode,
        reasons=tuple(reasons),
        action=action,
    )
