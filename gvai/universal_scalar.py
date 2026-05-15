from dataclasses import dataclass

@dataclass(frozen=True)
class GVEvidence:
    recovery_strength: float
    persistence: float
    directional_degradation: float
    volatility_penalty: float = 0.0

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

def gv_scalar(e: GVEvidence) -> float:
    recovery_strength = clamp01(e.recovery_strength)
    persistence = clamp01(e.persistence)
    directional_degradation = clamp01(e.directional_degradation)
    volatility_penalty = clamp01(e.volatility_penalty)

    continuity = (
        0.40 * recovery_strength
        + 0.35 * persistence
        + 0.20 * directional_degradation
        + 0.05 * (1.0 - volatility_penalty)
    )

    return round(clamp01(continuity), 6)
