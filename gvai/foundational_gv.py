from dataclasses import dataclass


@dataclass(frozen=True)
class ContinuityState:
    recovery: float
    persistence: float
    directional_integrity: float
    volatility: float = 0.0


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


def gv_foundation(state: ContinuityState):
    '''
    Foundational GV interpretation.

    GV is treated as a continuity constraint,
    not merely a fitted projection.

    Interpretation:
    A persistent system must preserve enough recoverability
    structure to remain dynamically coherent through time.
    '''

    recovery = clamp01(state.recovery)
    persistence = clamp01(state.persistence)
    directional_integrity = clamp01(state.directional_integrity)
    volatility = clamp01(state.volatility)

    continuity = (
        0.40 * recovery
        + 0.35 * persistence
        + 0.20 * directional_integrity
        + 0.05 * (1.0 - volatility)
    )

    return round(clamp01(continuity), 6)
