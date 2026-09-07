from gvai.postlabor.variables.registry import (
    get_variable,
    list_variables,
)
from gvai.postlabor.data.schema import (
    DataSource,
    Geography,
    GeographicSnapshot,
    Observation,
)
from gvai.postlabor.scoring.stability import score_snapshot
from gvai.postlabor.workers import (
    CareerCandidate,
    CurrentCareerAssessment,
    WorkerProfile,
    analyze_worker_transition,
)
from gvai.postlabor.workers.occupation_data import (
    OccupationRecord,
    OccupationSkill,
    skill_similarity,
)


def test_registry_counts():
    assert len(list_variables()) == 30
    assert len(list_variables(category="worker_transition")) == 10


def test_worker_registry_variable_exists():
    variable = get_variable(
        "worker_transition.career_resilience"
    )

    assert variable.category == "worker_transition"
    assert variable.direction == "higher_is_better"


def test_country_snapshot_scoring():
    geography = Geography(
        geo_id="TEST",
        name="Test Country",
    )

    source = DataSource(
        source_id="test",
        name="Test Source",
    )

    snapshot = GeographicSnapshot(
        geography=geography,
        as_of="2026-09-07",
    )

    values = {
        "demographics.fertility_rate": 1.8,
        "demographics.age_65_plus_share": 15.0,
        "demographics.working_age_share": 65.0,
        "demographics.old_age_dependency_ratio": 25.0,
        "labor.unemployment_rate": 5.0,
        "labor.participation_rate": 65.0,
        "economy.gdp_per_capita": 50_000.0,
    }

    for variable_id, value in values.items():
        snapshot.add(
            Observation(
                variable_id=variable_id,
                geography=geography,
                value=value,
                observed_at="2026-01-01",
                source=source,
                confidence=0.95,
            )
        )

    result = score_snapshot(snapshot)

    assert result.variables_used == 7
    assert result.variables_expected == 12
    assert 0.0 <= result.score <= 100.0
    assert result.confidence < 1.0

    automation = next(
        component
        for component in result.components
        if component.component == "automation_readiness"
    )

    assert automation.score is None
    assert automation.variables_used == 0
    assert automation.variables_expected == 3


def test_worker_transition_ranking():
    worker = WorkerProfile(
        occupation="Warehouse Worker",
        location="Murfreesboro, Tennessee",
        experience_years=8,
    )

    current = CurrentCareerAssessment(
        automation_displacement_pressure=72,
        augmentation_potential=48,
        demand_outlook=52,
        confidence=0.70,
    )

    stronger = CareerCandidate(
        occupation="Industrial Maintenance Technician",
        skill_transferability=76,
        demand_outlook=82,
        automation_displacement_pressure=25,
        retraining_burden=48,
        wage_retention=92,
        geographic_opportunity=84,
        confidence=0.72,
    )

    weaker = CareerCandidate(
        occupation="Example Lower Match",
        skill_transferability=45,
        demand_outlook=50,
        automation_displacement_pressure=60,
        retraining_burden=70,
        wage_retention=60,
        geographic_opportunity=50,
        confidence=0.70,
    )

    result = analyze_worker_transition(
        worker,
        current,
        [weaker, stronger],
    )

    assert result.current_career.score == 40.4
    assert (
        result.current_career.risk_band
        == "elevated_transition_risk"
    )

    assert result.opportunities[0].occupation == (
        "Industrial Maintenance Technician"
    )

    assert (
        result.opportunities[0].score
        > result.opportunities[1].score
    )


def test_skill_similarity():
    source = OccupationRecord(
        occupation_code="SOURCE",
        title="Source",
        skills=[
            OccupationSkill("1", "Mechanical", 80),
            OccupationSkill("2", "Troubleshooting", 70),
            OccupationSkill("3", "Customer Service", 50),
        ],
    )

    target = OccupationRecord(
        occupation_code="TARGET",
        title="Target",
        skills=[
            OccupationSkill("1", "Mechanical", 90),
            OccupationSkill("2", "Troubleshooting", 60),
            OccupationSkill("4", "Programming", 40),
        ],
    )

    assert skill_similarity(source, target) == 56.0
