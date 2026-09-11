from __future__ import annotations

STEX_RUBRIC_VERSION = "STEX v0.1"


def _validate_rating(name: str, value: int | float) -> float:
    value = float(value)

    if value < 0 or value > 4:
        raise ValueError(
            f"{name} must be between 0 and 4 inclusive; got {value}"
        )

    return value


def calculate_task_exposure(
    *,
    digital_capability: int | float,
    physical_execution: int | float,
    human_presence_requirement: int | float,
) -> float:
    """
    Calculate STEX v0.1 task structural exposure.

    Formula:

        C = max(D, P) / 4
        H = R / 4
        E = 100 * C * (1 - H)

    Returns:
        Exposure score bounded from 0.0 to 100.0.
    """

    d = _validate_rating(
        "digital_capability",
        digital_capability,
    )
    p = _validate_rating(
        "physical_execution",
        physical_execution,
    )
    r = _validate_rating(
        "human_presence_requirement",
        human_presence_requirement,
    )

    capability = max(d, p) / 4.0
    human_constraint = r / 4.0

    exposure = 100.0 * capability * (1.0 - human_constraint)

    return round(exposure, 4)
