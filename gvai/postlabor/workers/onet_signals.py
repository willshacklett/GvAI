from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from gvai.postlabor.sources.onet import (
    OnetClient,
    OnetWorkActivity,
    OnetWorkContext,
)
from gvai.postlabor.workers.onet_characteristics import (
    OccupationCharacteristics,
    derive_characteristics,
)


@dataclass(frozen=True)
class OnetSignals:
    physical_activity: float
    worksite_presence: float
    task_variability: float
    interpersonal_activity: float
    information_processing: float
    routine_activity: float
    coverage: float


# Each entry:
#   element_id: weight
#
# These mappings use standardized O*NET Content Model element IDs.
# No occupation-specific logic is used.

PHYSICAL_ACTIVITY: Dict[str, float] = {
    # Work activities
    "4.A.3.a.1": 0.24,  # Performing General Physical Activities
    "4.A.3.a.2": 0.20,  # Handling and Moving Objects
    "4.A.3.a.3": 0.10,  # Controlling Machines and Processes
    "4.A.3.a.4": 0.14,  # Operating Vehicles / Mechanized Equipment

    # Work context
    "4.C.2.d.1.b": 0.06,  # Standing
    "4.C.2.d.1.d": 0.07,  # Walking or Running
    "4.C.2.d.1.e": 0.05,  # Kneeling / Crouching / Stooping / Crawling
    "4.C.2.d.1.f": 0.03,  # Balance
    "4.C.2.d.1.g": 0.07,  # Using Hands / Tools / Controls
    "4.C.2.d.1.h": 0.04,  # Bending / Twisting
}


WORKSITE_PRESENCE: Dict[str, float] = {
    "4.C.2.a.1.b": 0.07,  # Indoors, not environmentally controlled
    "4.C.2.a.1.c": 0.15,  # Outdoors, exposed to weather
    "4.C.2.a.1.d": 0.06,  # Outdoors, under cover
    "4.C.2.a.1.e": 0.07,  # Open vehicle / equipment
    "4.C.2.a.1.f": 0.10,  # Enclosed vehicle / equipment
    "4.C.2.a.3": 0.08,    # Physical proximity
    "4.C.2.d.1.b": 0.06,  # Standing
    "4.C.2.d.1.d": 0.07,  # Walking / running
    "4.C.2.d.1.g": 0.08,  # Hands / tools / controls
    "4.C.1.a.2.l": 0.10,  # Face-to-face discussion
    "4.C.1.b.1.f": 0.08,  # External customers / public
    "4.C.2.e.1.d": 0.08,  # Common PPE
}


TASK_VARIABILITY: Dict[str, float] = {
    "4.A.1.b.1": 0.11,  # Identifying Objects, Actions, Events
    "4.A.1.b.2": 0.10,  # Inspecting Equipment / Structures / Materials
    "4.A.1.a.2": 0.08,  # Monitoring Processes / Materials / Surroundings
    "4.A.2.a.1": 0.07,  # Judging Qualities
    "4.A.2.b.1": 0.17,  # Decisions and Problem Solving
    "4.A.2.b.2": 0.10,  # Thinking Creatively
    "4.A.2.b.4": 0.07,  # Developing Objectives and Strategies
    "4.A.1.b.3": 0.05,  # Estimating Quantifiable Characteristics

    "4.C.3.a.2.b": 0.07,  # Frequency of Decision Making
    "4.C.3.a.4": 0.07,    # Freedom to Make Decisions
    "4.C.3.b.8": 0.06,    # Determine Tasks / Priorities / Goals
    "4.C.3.b.7": 0.05,    # Repeating Same Tasks -- inverted
}


INTERPERSONAL_ACTIVITY: Dict[str, float] = {
    "4.A.4.a.2": 0.08,  # Communicating internally
    "4.A.4.a.3": 0.10,  # Communicating externally
    "4.A.4.a.4": 0.08,  # Maintaining Relationships
    "4.A.4.a.5": 0.07,  # Assisting and Caring
    "4.A.4.a.6": 0.06,  # Selling / Influencing
    "4.A.4.a.7": 0.06,  # Resolving Conflict
    "4.A.4.a.8": 0.10,  # Working Directly with Public
    "4.A.4.b.1": 0.05,  # Coordinating Others
    "4.A.4.b.6": 0.05,  # Consultation / Advice

    "4.C.1.a.2.l": 0.09,  # Face-to-face Discussion
    "4.C.1.a.4": 0.08,    # Contact With Others
    "4.C.1.b.1.e": 0.04,  # Work Group / Team
    "4.C.1.b.1.f": 0.07,  # External Customers
    "4.C.1.d.1": 0.03,    # Conflict Situations
    "4.C.1.d.2": 0.04,    # Unpleasant / Angry People
}


INFORMATION_PROCESSING: Dict[str, float] = {
    "4.A.1.a.1": 0.13,  # Getting Information
    "4.A.2.a.2": 0.11,  # Processing Information
    "4.A.2.a.3": 0.08,  # Compliance Evaluation
    "4.A.2.a.4": 0.13,  # Analyzing Data / Information
    "4.A.2.b.1": 0.10,  # Decisions / Problem Solving
    "4.A.2.b.3": 0.10,  # Updating Knowledge
    "4.A.3.b.1": 0.12,  # Working With Computers
    "4.A.3.b.6": 0.09,  # Documenting Information
    "4.A.4.a.1": 0.07,  # Interpreting Information for Others
    "4.A.4.c.1": 0.07,  # Administrative Activities
}


ROUTINE_ACTIVITY: Dict[str, float] = {
    "4.C.3.b.7": 0.35,  # Importance of Repeating Same Tasks
    "4.C.2.d.1.i": 0.25,  # Repetitive Motions
    "4.C.3.d.3": 0.15,  # Pace Determined by Equipment
    "4.C.3.b.2": 0.10,  # Degree of Automation
    "4.C.3.b.4": 0.15,  # Exactness / Accuracy
}


# Elements whose contribution is reversed:
# high repetition -> low variability.
INVERT_FOR_VARIABILITY = {
    "4.C.3.b.7",
}


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _weighted_signal(
    values: Mapping[str, float],
    weights: Mapping[str, float],
    *,
    inverted: Iterable[str] = (),
) -> Tuple[float, float]:
    """
    Return:
        normalized signal score,
        fraction of expected weight for which O*NET supplied data.

    Missing descriptors are ignored rather than treated as zero.
    """
    inverted = set(inverted)

    weighted_total = 0.0
    available_weight = 0.0
    expected_weight = sum(weights.values())

    for element_id, weight in weights.items():
        if element_id not in values:
            continue

        value = _clamp(values[element_id])

        if element_id in inverted:
            value = 100.0 - value

        weighted_total += value * weight
        available_weight += weight

    if available_weight == 0:
        return 50.0, 0.0

    score = weighted_total / available_weight
    coverage = (
        available_weight / expected_weight
        if expected_weight
        else 0.0
    )

    return round(_clamp(score), 2), round(coverage, 4)


def build_onet_signals(
    activities: Sequence[OnetWorkActivity],
    contexts: Sequence[OnetWorkContext],
) -> OnetSignals:
    values: Dict[str, float] = {}

    for activity in activities:
        values[activity.element_id] = activity.importance

    for context in contexts:
        values[context.element_id] = context.context

    physical, physical_cov = _weighted_signal(
        values,
        PHYSICAL_ACTIVITY,
    )

    worksite, worksite_cov = _weighted_signal(
        values,
        WORKSITE_PRESENCE,
    )

    variability, variability_cov = _weighted_signal(
        values,
        TASK_VARIABILITY,
        inverted=INVERT_FOR_VARIABILITY,
    )

    interpersonal, interpersonal_cov = _weighted_signal(
        values,
        INTERPERSONAL_ACTIVITY,
    )

    information, information_cov = _weighted_signal(
        values,
        INFORMATION_PROCESSING,
    )

    routine, routine_cov = _weighted_signal(
        values,
        ROUTINE_ACTIVITY,
    )

    coverage = (
        physical_cov
        + worksite_cov
        + variability_cov
        + interpersonal_cov
        + information_cov
        + routine_cov
    ) / 6.0

    return OnetSignals(
        physical_activity=physical,
        worksite_presence=worksite,
        task_variability=variability,
        interpersonal_activity=interpersonal,
        information_processing=information,
        routine_activity=routine,
        coverage=round(coverage, 4),
    )


def occupation_characteristics_from_onet(
    occupation_code: str,
    *,
    client: OnetClient | None = None,
) -> OccupationCharacteristics:
    client = client or OnetClient()

    occupation = client.occupation(occupation_code)
    activities = client.work_activities(occupation_code)
    contexts = client.work_context(occupation_code)

    signals = build_onet_signals(
        activities,
        contexts,
    )

    # Confidence reflects source coverage, not confidence that
    # automation outcomes are certain.
    confidence = 0.55 + (0.35 * signals.coverage)

    return derive_characteristics(
        occupation_code=occupation.occupation_code,
        title=occupation.title,
        physical_activity=signals.physical_activity,
        worksite_presence=signals.worksite_presence,
        task_variability=signals.task_variability,
        interpersonal_activity=signals.interpersonal_activity,
        information_processing=signals.information_processing,
        routine_activity=signals.routine_activity,
        confidence=confidence,
    )
