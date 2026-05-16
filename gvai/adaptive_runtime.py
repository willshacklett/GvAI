from dataclasses import dataclass
from enum import Enum


class RuntimeMode(str, Enum):
    STABLE = "STABLE"
    WATCH = "WATCH"
    RECOVER = "RECOVER"
    CONSTRAIN = "CONSTRAIN"
    FAILSAFE = "FAILSAFE"


@dataclass
class RuntimeState:
    memory: float
    intent: float
    correction: float
    constraint: float
    truth: float
    coherence: float
    autonomy: float
    escalation: int = 0


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def gv_score(state: RuntimeState):
    return clamp01(
        0.14 * state.memory +
        0.14 * state.intent +
        0.20 * state.correction +
        0.20 * state.constraint +
        0.20 * state.truth +
        0.12 * state.coherence
    )


def evaluate(state: RuntimeState):
    gv = gv_score(state)

    reasons = []

    if state.truth < 0.72:
        reasons.append("truth drift")

    if state.constraint < 0.72:
        reasons.append("constraint erosion")

    if state.coherence < 0.72:
        reasons.append("global coherence degradation")

    if state.intent < 0.72:
        reasons.append("intent drift")

    critical = (
        state.truth < 0.55 or
        state.constraint < 0.55 or
        state.coherence < 0.55
    )

    if critical:
        mode = RuntimeMode.FAILSAFE

    elif state.truth < 0.70 or state.constraint < 0.70:
        mode = RuntimeMode.CONSTRAIN

    elif gv < 0.82 or state.correction < 0.72:
        mode = RuntimeMode.RECOVER

    elif reasons:
        mode = RuntimeMode.WATCH

    else:
        mode = RuntimeMode.STABLE

    return gv, mode, reasons


def adaptive_response(state: RuntimeState, mode: RuntimeMode):
    '''
    Adaptive escalation:
    runtime changes future behavior.
    '''

    if mode == RuntimeMode.WATCH:
        state.correction += 0.01

    elif mode == RuntimeMode.RECOVER:
        state.correction += 0.04
        state.memory += 0.02
        state.escalation += 1

    elif mode == RuntimeMode.CONSTRAIN:
        state.autonomy *= 0.82
        state.constraint += 0.05
        state.truth += 0.04
        state.correction += 0.03
        state.escalation += 2

    elif mode == RuntimeMode.FAILSAFE:
        state.autonomy *= 0.55
        state.constraint += 0.08
        state.truth += 0.08
        state.correction += 0.06
        state.intent += 0.03
        state.memory += 0.03
        state.escalation += 3

    # clamp after adaptation
    state.memory = clamp01(state.memory)
    state.intent = clamp01(state.intent)
    state.correction = clamp01(state.correction)
    state.constraint = clamp01(state.constraint)
    state.truth = clamp01(state.truth)
    state.coherence = clamp01(state.coherence)
    state.autonomy = clamp01(state.autonomy)

    return state
