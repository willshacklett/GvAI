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


def test_bls_series_latest():
    from gvai.postlabor.sources.bls import (
        BLSDatapoint,
        BLSSeries,
    )

    series = BLSSeries(
        series_id="TEST",
        data=[
            BLSDatapoint(
                series_id="TEST",
                year=2025,
                period="M12",
                value=10.0,
            ),
            BLSDatapoint(
                series_id="TEST",
                year=2026,
                period="M01",
                value=11.0,
            ),
        ],
    )

    latest = series.latest()

    assert latest is not None
    assert latest.year == 2026
    assert latest.period == "M01"
    assert latest.value == 11.0


def test_worker_transition_api():
    from flask import Flask
    from gvai.postlabor.api import postlabor_api

    app = Flask(__name__)
    app.register_blueprint(postlabor_api)

    client = app.test_client()

    response = client.post(
        "/api/postlabor/worker/transition",
        json={
            "occupation": "Warehouse Worker",
            "location": "Murfreesboro, Tennessee",
            "experience_years": 8,
            "current_assessment": {
                "automation_displacement_pressure": 72,
                "augmentation_potential": 48,
                "demand_outlook": 52,
                "confidence": 0.70,
            },
            "candidates": [
                {
                    "occupation": "Industrial Maintenance Technician",
                    "skill_transferability": 76,
                    "demand_outlook": 82,
                    "automation_displacement_pressure": 25,
                    "retraining_burden": 48,
                    "wage_retention": 92,
                    "geographic_opportunity": 84,
                    "confidence": 0.72,
                }
            ],
        },
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["ok"] is True

    result = payload["result"]

    assert result["current_career"]["score"] == 40.4
    assert (
        result["opportunities"][0]["occupation"]
        == "Industrial Maintenance Technician"
    )


def test_demand_outlook_score():
    from gvai.postlabor.workers.occupation_market import (
        OccupationMarketRecord,
        demand_outlook_score,
    )

    record = OccupationMarketRecord(
        soc_code="00-0001",
        title="Test Occupation",
        employment_base_thousands=100.0,
        employment_projected_thousands=110.0,
        employment_change_percent=10.0,
        annual_openings_thousands=10.0,
        median_annual_wage=60000.0,
    )

    score = demand_outlook_score(record)

    assert 0.0 <= score <= 100.0
    assert score > 50.0


def test_wage_retention_score():
    from gvai.postlabor.workers.occupation_market import (
        wage_retention_score,
    )

    assert wage_retention_score(
        current_annual_wage=50000,
        candidate_annual_wage=60000,
    ) == 100.0

    assert wage_retention_score(
        current_annual_wage=50000,
        candidate_annual_wage=40000,
    ) == 80.0


def test_retraining_burden_score():
    from gvai.postlabor.workers.occupation_market import (
        OccupationMarketRecord,
        retraining_burden_score,
    )

    low = OccupationMarketRecord(
        soc_code="A",
        title="Low",
        education="High school diploma or equivalent",
        on_the_job_training="Short-term on-the-job training",
    )

    high = OccupationMarketRecord(
        soc_code="B",
        title="High",
        education="Master's degree",
        on_the_job_training="Internship/residency",
    )

    assert retraining_burden_score(low) < retraining_burden_score(high)


def test_soc_crosswalk_fallback():
    from gvai.postlabor.workers.soc_crosswalk import (
        SOCCrosswalk,
        SOCCrosswalkRecord,
    )

    crosswalk = SOCCrosswalk(
        [
            SOCCrosswalkRecord(
                onet_soc_code="15-1252.00",
                bls_soc_code="15-1252",
            )
        ]
    )

    assert crosswalk.best_bls_soc(
        "15-1252.00"
    ) == "15-1252"


def test_build_candidate_from_market():
    from gvai.postlabor.workers.candidate_builder import (
        build_candidate_from_market,
    )
    from gvai.postlabor.workers.occupation_market import (
        OccupationMarketRecord,
    )

    record = OccupationMarketRecord(
        soc_code="49-9041",
        title="Industrial Machinery Mechanics",
        employment_base_thousands=400.0,
        employment_projected_thousands=450.0,
        employment_change_percent=12.5,
        annual_openings_thousands=40.0,
        median_annual_wage=65000.0,
        education="High school diploma or equivalent",
        on_the_job_training="Long-term on-the-job training",
    )

    candidate = build_candidate_from_market(
        record=record,
        current_annual_wage=50000.0,
        skill_transferability=78.0,
        automation_displacement_pressure=25.0,
        geographic_opportunity=80.0,
        confidence=0.8,
    )

    assert candidate.occupation == "Industrial Machinery Mechanics"
    assert candidate.demand_outlook > 50.0
    assert candidate.wage_retention == 100.0
    assert 0.0 <= candidate.retraining_burden <= 100.0


def test_occupation_search():
    from gvai.postlabor.workers.occupation_market import (
        OccupationMarketRecord,
    )
    from gvai.postlabor.workers.occupation_search import (
        find_by_soc,
        search_occupations,
    )

    records = [
        OccupationMarketRecord(
            soc_code="49-9041",
            title="Industrial Machinery Mechanics",
        ),
        OccupationMarketRecord(
            soc_code="49-9071",
            title="Maintenance and Repair Workers, General",
        ),
        OccupationMarketRecord(
            soc_code="11-2021",
            title="Marketing Managers",
        ),
    ]

    results = search_occupations(
        records,
        "industrial machinery",
    )

    assert results
    assert results[0].soc_code == "49-9041"

    found = find_by_soc(
        records,
        "49-9071",
    )

    assert found is not None
    assert found.title == "Maintenance and Repair Workers, General"


def test_market_recommender_uses_bls_fields():
    from gvai.postlabor.workers.market_recommender import (
        CandidateInputs,
        build_market_candidates,
    )
    from gvai.postlabor.workers.occupation_market import (
        OccupationMarketRecord,
    )

    record = OccupationMarketRecord(
        soc_code="49-9041",
        title="Industrial Machinery Mechanics",
        employment_base_thousands=400,
        employment_projected_thousands=450,
        employment_change_percent=12.5,
        annual_openings_thousands=40,
        median_annual_wage=65000,
        education="High school diploma or equivalent",
        on_the_job_training="Long-term on-the-job training",
    )

    candidates = build_market_candidates(
        candidate_records=[record],
        current_annual_wage=50000,
        inputs_by_soc={
            "49-9041": CandidateInputs(
                skill_transferability=78,
                automation_displacement_pressure=25,
                geographic_opportunity=80,
                confidence=0.8,
            )
        },
    )

    assert len(candidates) == 1

    candidate = candidates[0]

    assert candidate.occupation == "Industrial Machinery Mechanics"
    assert candidate.demand_outlook > 50
    assert candidate.wage_retention == 100
    assert candidate.skill_transferability == 78
