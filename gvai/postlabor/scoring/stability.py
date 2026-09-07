from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from gvai.postlabor.data.schema import GeographicSnapshot
from gvai.postlabor.variables.registry import get_variable


@dataclass(frozen=True)
class NormalizationRule:
    variable_id: str
    component: str
    lower_bound: float
    upper_bound: float
    weight: float = 1.0


@dataclass(frozen=True)
class ScoredVariable:
    variable_id: str
    component: str
    raw_value: float
    normalized_score: float
    weight: float
    confidence: float
    contribution: float
    unit: str
    direction: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComponentResult:
    component: str
    score: Optional[float]
    confidence: float
    coverage: float
    variables_used: int
    variables_expected: int
    missing_variables: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StabilityResult:
    geo_id: str
    geography_name: str
    score: float
    confidence: float
    coverage: float
    variables_used: int
    variables_expected: int
    missing_variables: List[str]
    components: List[ComponentResult]
    variables: List[ScoredVariable]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "geo_id": self.geo_id,
            "geography_name": self.geography_name,
            "score": self.score,
            "confidence": self.confidence,
            "coverage": self.coverage,
            "variables_used": self.variables_used,
            "variables_expected": self.variables_expected,
            "missing_variables": self.missing_variables,
            "components": [c.to_dict() for c in self.components],
            "variables": [v.to_dict() for v in self.variables],
        }


DEFAULT_RULES: List[NormalizationRule] = [

    # Demographic Resilience
    NormalizationRule(
        "demographics.fertility_rate",
        "demographic_resilience",
        1.0,
        2.1,
        1.0,
    ),
    NormalizationRule(
        "demographics.age_65_plus_share",
        "demographic_resilience",
        5.0,
        30.0,
        1.0,
    ),
    NormalizationRule(
        "demographics.working_age_share",
        "demographic_resilience",
        50.0,
        70.0,
        1.0,
    ),
    NormalizationRule(
        "demographics.old_age_dependency_ratio",
        "demographic_resilience",
        10.0,
        50.0,
        1.0,
    ),

    # Labor Resilience
    NormalizationRule(
        "labor.unemployment_rate",
        "labor_resilience",
        2.0,
        15.0,
        1.0,
    ),
    NormalizationRule(
        "labor.participation_rate",
        "labor_resilience",
        45.0,
        75.0,
        1.0,
    ),

    # Economic Capacity
    NormalizationRule(
        "economy.gdp_per_capita",
        "economic_capacity",
        5_000.0,
        80_000.0,
        1.0,
    ),

    # Automation Readiness
    NormalizationRule(
        "automation.ai_adoption",
        "automation_readiness",
        0.0,
        100.0,
        1.0,
    ),
    NormalizationRule(
        "automation.robot_density",
        "automation_readiness",
        0.0,
        1000.0,
        1.0,
    ),
    NormalizationRule(
        "automation.task_exposure",
        "automation_readiness",
        0.0,
        100.0,
        1.0,
    ),

    # Fiscal Resilience
    NormalizationRule(
        "government.debt_to_gdp",
        "fiscal_resilience",
        20.0,
        150.0,
        1.0,
    ),

    # Distribution Resilience
    NormalizationRule(
        "capital.labor_share_income",
        "distribution_resilience",
        35.0,
        65.0,
        1.0,
    ),
]


COMPONENT_ORDER = [
    "demographic_resilience",
    "labor_resilience",
    "economic_capacity",
    "automation_readiness",
    "fiscal_resilience",
    "distribution_resilience",
]


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def normalize_linear(
    *,
    value: float,
    lower_bound: float,
    upper_bound: float,
    direction: str,
) -> float:
    if upper_bound <= lower_bound:
        raise ValueError("upper_bound must be greater than lower_bound")

    bounded = clamp(value, lower_bound, upper_bound)

    position = (
        (bounded - lower_bound)
        / (upper_bound - lower_bound)
    )

    if direction == "higher_is_better":
        score = position * 100.0

    elif direction == "higher_is_worse":
        score = (1.0 - position) * 100.0

    else:
        score = 50.0

    return round(score, 2)


def explanation_for(
    variable_id: str,
    raw_value: float,
    normalized_score: float,
) -> str:
    variable = get_variable(variable_id)

    if variable.direction == "higher_is_better":
        relation = "Higher values generally improve resilience in this model."
    elif variable.direction == "higher_is_worse":
        relation = "Higher values generally increase structural pressure in this model."
    else:
        relation = (
            "This variable is context-dependent and is not yet treated "
            "as strictly positive or negative."
        )

    return (
        f"{variable.name}: observed value {raw_value} {variable.unit}. "
        f"Normalized resilience score {normalized_score}/100. "
        f"{relation}"
    )


def _score_component(
    component_name: str,
    scored_variables: List[ScoredVariable],
    rules: List[NormalizationRule],
) -> ComponentResult:

    component_rules = [
        rule for rule in rules
        if rule.component == component_name
    ]

    component_variables = [
        item for item in scored_variables
        if item.component == component_name
    ]

    expected_ids = {
        rule.variable_id
        for rule in component_rules
    }

    present_ids = {
        item.variable_id
        for item in component_variables
    }

    missing = sorted(expected_ids - present_ids)

    variables_expected = len(component_rules)
    variables_used = len(component_variables)

    coverage = (
        variables_used / variables_expected
        if variables_expected
        else 0.0
    )

    if not component_variables:
        return ComponentResult(
            component=component_name,
            score=None,
            confidence=0.0,
            coverage=0.0,
            variables_used=0,
            variables_expected=variables_expected,
            missing_variables=missing,
        )

    weighted_sum = sum(
        item.normalized_score * item.weight * item.confidence
        for item in component_variables
    )

    weight_sum = sum(
        item.weight * item.confidence
        for item in component_variables
    )

    score = (
        weighted_sum / weight_sum
        if weight_sum
        else 0.0
    )

    average_confidence = (
        sum(item.confidence for item in component_variables)
        / variables_used
    )

    confidence = average_confidence * coverage

    return ComponentResult(
        component=component_name,
        score=round(score, 2),
        confidence=round(confidence, 4),
        coverage=round(coverage, 4),
        variables_used=variables_used,
        variables_expected=variables_expected,
        missing_variables=missing,
    )


def score_snapshot(
    snapshot: GeographicSnapshot,
    rules: Optional[List[NormalizationRule]] = None,
) -> StabilityResult:

    rules = rules or DEFAULT_RULES

    scored_variables: List[ScoredVariable] = []
    missing: List[str] = []

    for rule in rules:
        observation = snapshot.get(rule.variable_id)

        if observation is None:
            missing.append(rule.variable_id)
            continue

        variable = get_variable(rule.variable_id)

        normalized = normalize_linear(
            value=observation.value,
            lower_bound=rule.lower_bound,
            upper_bound=rule.upper_bound,
            direction=variable.direction,
        )

        contribution = (
            normalized
            * rule.weight
            * observation.confidence
        )

        scored_variables.append(
            ScoredVariable(
                variable_id=rule.variable_id,
                component=rule.component,
                raw_value=observation.value,
                normalized_score=normalized,
                weight=rule.weight,
                confidence=observation.confidence,
                contribution=round(contribution, 4),
                unit=variable.unit,
                direction=variable.direction,
                explanation=explanation_for(
                    rule.variable_id,
                    observation.value,
                    normalized,
                ),
            )
        )

    component_names = list(dict.fromkeys(
        COMPONENT_ORDER
        + [rule.component for rule in rules]
    ))

    components = [
        _score_component(
            component_name,
            scored_variables,
            rules,
        )
        for component_name in component_names
    ]

    available_components = [
        component
        for component in components
        if component.score is not None
    ]

    # v0.2: headline score is the equal-weight mean of available component
    # scores, rather than allowing components with more variables to dominate.
    if available_components:
        score = sum(
            component.score
            for component in available_components
            if component.score is not None
        ) / len(available_components)
    else:
        score = 0.0

    variables_expected = len(rules)
    variables_used = len(scored_variables)

    coverage = (
        variables_used / variables_expected
        if variables_expected
        else 0.0
    )

    if available_components:
        mean_component_confidence = (
            sum(component.confidence for component in available_components)
            / len(available_components)
        )
    else:
        mean_component_confidence = 0.0

    overall_confidence = mean_component_confidence * coverage

    return StabilityResult(
        geo_id=snapshot.geography.geo_id,
        geography_name=snapshot.geography.name,
        score=round(score, 2),
        confidence=round(overall_confidence, 4),
        coverage=round(coverage, 4),
        variables_used=variables_used,
        variables_expected=variables_expected,
        missing_variables=sorted(missing),
        components=components,
        variables=scored_variables,
    )
