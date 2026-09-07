from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Literal, Optional


VariableKind = Literal["observed", "derived", "scenario"]
Direction = Literal[
    "higher_is_better",
    "higher_is_worse",
    "context_dependent",
    "neutral",
]


@dataclass(frozen=True)
class VariableDefinition:
    """
    Canonical definition for one variable used by the Post-Labor engine.

    A variable definition describes what a measurement means.
    It does not contain a country/company's actual measured value.
    """

    variable_id: str
    name: str
    category: str
    definition: str
    unit: str

    kind: VariableKind = "observed"
    direction: Direction = "context_dependent"

    source_hint: str = ""
    update_frequency: str = "unknown"
    geographic_resolution: str = "country"

    weight: float = 1.0
    default_confidence: float = 0.75

    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


_REGISTRY: Dict[str, VariableDefinition] = {}


def register_variable(variable: VariableDefinition) -> None:
    """
    Register a canonical variable.

    Duplicate IDs are rejected so that a score can never silently change
    meaning because two variables happen to share an identifier.
    """
    if not variable.variable_id:
        raise ValueError("variable_id cannot be empty")

    if variable.variable_id in _REGISTRY:
        raise ValueError(
            f"Variable already registered: {variable.variable_id}"
        )

    if not 0.0 <= variable.default_confidence <= 1.0:
        raise ValueError(
            f"default_confidence must be between 0 and 1: "
            f"{variable.variable_id}"
        )

    if variable.weight < 0:
        raise ValueError(
            f"weight cannot be negative: {variable.variable_id}"
        )

    _REGISTRY[variable.variable_id] = variable


def get_variable(variable_id: str) -> VariableDefinition:
    try:
        return _REGISTRY[variable_id]
    except KeyError as exc:
        raise KeyError(f"Unknown Post-Labor variable: {variable_id}") from exc


def find_variable(variable_id: str) -> Optional[VariableDefinition]:
    return _REGISTRY.get(variable_id)


def list_variables(
    *,
    category: Optional[str] = None,
    kind: Optional[VariableKind] = None,
) -> List[VariableDefinition]:
    variables: Iterable[VariableDefinition] = _REGISTRY.values()

    if category is not None:
        variables = (v for v in variables if v.category == category)

    if kind is not None:
        variables = (v for v in variables if v.kind == kind)

    return sorted(variables, key=lambda v: v.variable_id)


def registry_as_dict() -> Dict[str, dict]:
    return {
        variable.variable_id: variable.to_dict()
        for variable in list_variables()
    }


# ---------------------------------------------------------------------------
# Canonical seed variables
#
# These are deliberately broad, high-value variables that we expect to have
# dependable public data for. The registry will grow substantially, but every
# additional variable should be explicit, sourced, and explainable.
# ---------------------------------------------------------------------------

SEED_VARIABLES = [

    # -----------------------------------------------------------------------
    # DEMOGRAPHICS
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="demographics.fertility_rate",
        name="Total Fertility Rate",
        category="demographics",
        definition=(
            "Average number of children expected to be born per woman "
            "under current age-specific fertility rates."
        ),
        unit="births_per_woman",
        direction="context_dependent",
        source_hint="UN World Population Prospects / World Bank",
        update_frequency="annual",
        geographic_resolution="country",
        notes=(
            "Very low fertility can increase long-run labor scarcity and "
            "dependency pressure."
        ),
    ),

    VariableDefinition(
        variable_id="demographics.age_65_plus_share",
        name="Population Age 65+ Share",
        category="demographics",
        definition="Share of total population aged 65 years or older.",
        unit="percent",
        direction="higher_is_worse",
        source_hint="UN World Population Prospects / World Bank",
        update_frequency="annual",
        geographic_resolution="country",
    ),

    VariableDefinition(
        variable_id="demographics.working_age_share",
        name="Working-Age Population Share",
        category="demographics",
        definition=(
            "Share of population generally considered working age."
        ),
        unit="percent",
        direction="higher_is_better",
        source_hint="UN / World Bank",
        update_frequency="annual",
        geographic_resolution="country",
    ),

    VariableDefinition(
        variable_id="demographics.old_age_dependency_ratio",
        name="Old-Age Dependency Ratio",
        category="demographics",
        definition=(
            "Ratio of older dependents to the working-age population."
        ),
        unit="ratio",
        direction="higher_is_worse",
        source_hint="World Bank / UN",
        update_frequency="annual",
        geographic_resolution="country",
    ),

    # -----------------------------------------------------------------------
    # LABOR
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="labor.unemployment_rate",
        name="Unemployment Rate",
        category="labor",
        definition=(
            "Share of the labor force that is unemployed and actively "
            "seeking work."
        ),
        unit="percent",
        direction="higher_is_worse",
        source_hint="ILO / national statistical agencies / World Bank",
        update_frequency="monthly_or_quarterly",
        geographic_resolution="country",
    ),

    VariableDefinition(
        variable_id="labor.participation_rate",
        name="Labor Force Participation Rate",
        category="labor",
        definition=(
            "Share of the working-age population participating in the "
            "labor force."
        ),
        unit="percent",
        direction="higher_is_better",
        source_hint="ILO / World Bank / national statistical agencies",
        update_frequency="monthly_or_quarterly",
        geographic_resolution="country",
    ),

    VariableDefinition(
        variable_id="labor.vacancy_pressure",
        name="Labor Vacancy Pressure",
        category="labor",
        definition=(
            "Degree to which unfilled jobs indicate persistent labor scarcity."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_worse",
        source_hint="Derived from vacancy, hiring and unemployment data",
        update_frequency="monthly",
        geographic_resolution="country",
        notes=(
            "High vacancy pressure can accelerate automation even without "
            "traditional displacement incentives."
        ),
    ),

    # -----------------------------------------------------------------------
    # AUTOMATION
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="automation.ai_adoption",
        name="AI Adoption",
        category="automation",
        definition=(
            "Estimated penetration of AI systems within firms and productive "
            "economic activity."
        ),
        unit="index_0_100",
        kind="derived",
        direction="context_dependent",
        source_hint=(
            "Enterprise surveys, technology adoption statistics, "
            "company disclosures"
        ),
        update_frequency="quarterly",
        geographic_resolution="country",
    ),

    VariableDefinition(
        variable_id="automation.robot_density",
        name="Industrial Robot Density",
        category="automation",
        definition=(
            "Industrial robots deployed relative to manufacturing employment."
        ),
        unit="robots_per_10000_workers",
        direction="context_dependent",
        source_hint="International Federation of Robotics",
        update_frequency="annual",
        geographic_resolution="country",
    ),

    VariableDefinition(
        variable_id="automation.task_exposure",
        name="Employment Task Automation Exposure",
        category="automation",
        definition=(
            "Estimated share of employment activity exposed to feasible "
            "AI or robotic automation."
        ),
        unit="percent",
        kind="derived",
        direction="higher_is_worse",
        source_hint=(
            "Occupation/task datasets combined with automation capability "
            "estimates"
        ),
        update_frequency="quarterly",
        geographic_resolution="country",
    ),

    # -----------------------------------------------------------------------
    # HOUSEHOLDS
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="household.labor_income_dependency",
        name="Household Labor-Income Dependency",
        category="household",
        definition=(
            "Degree to which household purchasing power depends directly "
            "on wages and salaries."
        ),
        unit="percent",
        kind="derived",
        direction="higher_is_worse",
        source_hint="National accounts / household income surveys",
        update_frequency="annual_or_quarterly",
        geographic_resolution="country",
        notes=(
            "One of the central variables in the Post-Labor model."
        ),
    ),

    VariableDefinition(
        variable_id="household.savings_resilience",
        name="Household Savings Resilience",
        category="household",
        definition=(
            "Estimated household capacity to absorb an income shock using "
            "liquid savings and disposable resources."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint="Household balance sheets / savings / debt data",
        update_frequency="quarterly",
        geographic_resolution="country",
    ),

    # -----------------------------------------------------------------------
    # CAPITAL / DISTRIBUTION
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="capital.ownership_concentration",
        name="Capital Ownership Concentration",
        category="capital",
        definition=(
            "Degree to which productive and financial capital ownership is "
            "concentrated among a small share of households."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_worse",
        source_hint="Wealth distribution datasets / household balance sheets",
        update_frequency="annual",
        geographic_resolution="country",
    ),

    VariableDefinition(
        variable_id="capital.labor_share_income",
        name="Labor Share of Income",
        category="capital",
        definition=(
            "Share of national income accruing to labor compensation."
        ),
        unit="percent",
        direction="context_dependent",
        source_hint="ILO / OECD / national accounts",
        update_frequency="annual_or_quarterly",
        geographic_resolution="country",
    ),

    # -----------------------------------------------------------------------
    # GOVERNMENT
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="government.debt_to_gdp",
        name="Government Debt to GDP",
        category="government",
        definition=(
            "Gross government debt relative to annual economic output."
        ),
        unit="percent_gdp",
        direction="higher_is_worse",
        source_hint="IMF / World Bank / national finance ministries",
        update_frequency="quarterly_or_annual",
        geographic_resolution="country",
    ),

    VariableDefinition(
        variable_id="government.fiscal_capacity",
        name="Fiscal Response Capacity",
        category="government",
        definition=(
            "Estimated ability of government to support households and the "
            "economy during structural labor-market disruption."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint=(
            "Derived from fiscal balance, debt service, tax capacity and "
            "social protection data"
        ),
        update_frequency="quarterly",
        geographic_resolution="country",
    ),

    # -----------------------------------------------------------------------
    # ENERGY
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="energy.electricity_capacity",
        name="Electricity System Capacity",
        category="energy",
        definition=(
            "Ability of the electricity system to support expanding "
            "industrial, robotic, computing and data-center demand."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint="IEA / EIA / national energy agencies",
        update_frequency="monthly_or_annual",
        geographic_resolution="country",
    ),

    # -----------------------------------------------------------------------
    # ECONOMY
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="economy.gdp_per_capita",
        name="GDP per Capita",
        category="economy",
        definition="Economic output per person.",
        unit="usd_per_person",
        direction="higher_is_better",
        source_hint="World Bank / IMF",
        update_frequency="annual_or_quarterly",
        geographic_resolution="country",
    ),

    VariableDefinition(
        variable_id="economy.productivity_growth",
        name="Labor Productivity Growth",
        category="economy",
        definition=(
            "Change in economic output produced per unit of labor input."
        ),
        unit="percent_change",
        direction="context_dependent",
        source_hint="OECD / ILO / national accounts",
        update_frequency="quarterly_or_annual",
        geographic_resolution="country",
    ),

    # -----------------------------------------------------------------------
    # SOCIAL TRANSITION
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="social.transition_stress",
        name="Social Transition Stress",
        category="social",
        definition=(
            "Composite measure of economic and social strain associated with "
            "labor-market and structural economic transition."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_worse",
        source_hint=(
            "Derived from unemployment, household stress, housing pressure, "
            "income disruption and related indicators"
        ),
        update_frequency="monthly_or_quarterly",
        geographic_resolution="country",
        notes=(
            "This is a structural stress indicator, not a prediction of "
            "political violence or collapse."
        ),
    ),


    # -----------------------------------------------------------------------
    # WORKER TRANSITION
    # -----------------------------------------------------------------------
    VariableDefinition(
        variable_id="worker_transition.automation_displacement_pressure",
        name="Automation Displacement Pressure",
        category="worker_transition",
        definition=(
            "Estimated pressure on human labor demand within an occupation "
            "from AI, software, robotics, and other automation."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_worse",
        source_hint="O*NET tasks + BLS employment data + automation capability models",
        update_frequency="quarterly",
        geographic_resolution="occupation",
    ),

    VariableDefinition(
        variable_id="worker_transition.augmentation_potential",
        name="Automation Augmentation Potential",
        category="worker_transition",
        definition=(
            "Estimated degree to which automation increases worker productivity "
            "without materially eliminating the occupation."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint="O*NET tasks + AI capability models",
        update_frequency="quarterly",
        geographic_resolution="occupation",
    ),

    VariableDefinition(
        variable_id="worker_transition.demand_outlook",
        name="Occupation Demand Outlook",
        category="worker_transition",
        definition=(
            "Expected strength of future demand for workers in an occupation."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint="BLS employment projections + labor-market data",
        update_frequency="annual_or_quarterly",
        geographic_resolution="occupation",
    ),

    VariableDefinition(
        variable_id="worker_transition.skill_transferability",
        name="Skill Transferability",
        category="worker_transition",
        definition=(
            "Degree to which skills from a worker's current occupation transfer "
            "to a candidate destination occupation."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint="O*NET skills, knowledge, abilities and work activities",
        update_frequency="annual",
        geographic_resolution="occupation_pair",
    ),

    VariableDefinition(
        variable_id="worker_transition.retraining_burden",
        name="Retraining Burden",
        category="worker_transition",
        definition=(
            "Estimated training, credential, education, time and cost burden "
            "required to transition into a destination occupation."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_worse",
        source_hint="O*NET education + credentials + training requirements",
        update_frequency="annual",
        geographic_resolution="occupation_pair",
    ),

    VariableDefinition(
        variable_id="worker_transition.wage_retention",
        name="Wage Retention",
        category="worker_transition",
        definition=(
            "Expected ability of a worker to preserve or improve earnings "
            "after moving into a destination occupation."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint="BLS wage data + regional wage estimates",
        update_frequency="annual_or_quarterly",
        geographic_resolution="occupation_geography",
    ),

    VariableDefinition(
        variable_id="worker_transition.geographic_opportunity",
        name="Geographic Opportunity",
        category="worker_transition",
        definition=(
            "Availability of viable employment opportunities for a destination "
            "occupation within the worker's geographic constraints."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint="BLS local employment + live job postings",
        update_frequency="daily_or_monthly",
        geographic_resolution="occupation_geography",
    ),

    VariableDefinition(
        variable_id="worker_transition.transition_urgency",
        name="Transition Urgency",
        category="worker_transition",
        definition=(
            "Estimated urgency for a worker to begin preparing for occupational "
            "change based on displacement pressure, demand and augmentation."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_worse",
        source_hint="Derived by GvAI Worker Transition Engine",
        update_frequency="on_analysis",
        geographic_resolution="worker",
    ),

    VariableDefinition(
        variable_id="worker_transition.career_resilience",
        name="Career Resilience",
        category="worker_transition",
        definition=(
            "Estimated resilience of the worker's current occupation under "
            "technological and labor-market transition."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint="Derived by GvAI Worker Transition Engine",
        update_frequency="on_analysis",
        geographic_resolution="worker",
    ),

    VariableDefinition(
        variable_id="worker_transition.transition_opportunity",
        name="Transition Opportunity",
        category="worker_transition",
        definition=(
            "Composite attractiveness of a candidate destination occupation "
            "for a specific worker."
        ),
        unit="index_0_100",
        kind="derived",
        direction="higher_is_better",
        source_hint="Derived by GvAI Worker Transition Engine",
        update_frequency="on_analysis",
        geographic_resolution="worker_occupation_pair",
    ),
]


for _variable in SEED_VARIABLES:
    register_variable(_variable)
