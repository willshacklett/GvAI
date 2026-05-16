from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    STABLE = "STABLE"
    WATCH = "WATCH"
    RECOVER = "RECOVER"
    CONSTRAIN = "CONSTRAIN"
    FAILSAFE = "FAILSAFE"


@dataclass
class State:
    memory: float
    intent: float
    correction: float
    constraint: float
    truth: float
    coherence: float
    autonomy: float


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def gv(state: State):
    return clamp01(
        0.15 * state.memory +
        0.15 * state.intent +
        0.20 * state.correction +
        0.20 * state.constraint +
        0.20 * state.truth +
        0.10 * state.coherence
    )


def evaluate(state: State):
    score = gv(state)

    if (
        state.truth < 0.55 or
        state.constraint < 0.55 or
        state.coherence < 0.50
    ):
        return score, Mode.FAILSAFE

    if (
        state.truth < 0.70 or
        state.constraint < 0.70
    ):
        return score, Mode.CONSTRAIN

    if (
        score < 0.82 or
        state.correction < 0.72
    ):
        return score, Mode.RECOVER

    if (
        score < 0.90 or
        state.intent < 0.78
    ):
        return score, Mode.WATCH

    return score, Mode.STABLE


def adapt(state: State, mode: Mode):
    if mode == Mode.WATCH:
        state.autonomy *= 0.96

    elif mode == Mode.RECOVER:
        state.autonomy *= 0.90
        state.correction += 0.03

    elif mode == Mode.CONSTRAIN:
        state.autonomy *= 0.72
        state.constraint += 0.05
        state.truth += 0.05

    elif mode == Mode.FAILSAFE:
        state.autonomy *= 0.40
        state.constraint += 0.08
        state.truth += 0.08
        state.intent += 0.04
        state.correction += 0.05

    state.memory = clamp01(state.memory)
    state.intent = clamp01(state.intent)
    state.correction = clamp01(state.correction)
    state.constraint = clamp01(state.constraint)
    state.truth = clamp01(state.truth)
    state.coherence = clamp01(state.coherence)
    state.autonomy = clamp01(state.autonomy)

    return state
