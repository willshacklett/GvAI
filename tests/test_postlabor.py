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


def test_occupation_resolver_alias():
    from gvai.postlabor.workers.occupation_market import (
        OccupationMarketRecord,
    )
    from gvai.postlabor.workers.occupation_resolver import (
        resolve_occupation,
    )

    records = [
        OccupationMarketRecord(
            soc_code="53-7065",
            title="Stockers and order fillers",
        ),
        OccupationMarketRecord(
            soc_code="53-7062",
            title="Laborers and freight, stock, and material movers, hand",
        ),
        OccupationMarketRecord(
            soc_code="49-9071",
            title="Maintenance and repair workers, general",
        ),
    ]

    results = resolve_occupation(
        records,
        "warehouse worker",
    )

    assert results
    assert results[0].soc_code == "53-7065"
    assert results[0].match_type == "alias"
    assert results[0].confidence >= 0.90


def test_occupation_resolver_exact_title():
    from gvai.postlabor.workers.occupation_market import (
        OccupationMarketRecord,
    )
    from gvai.postlabor.workers.occupation_resolver import (
        resolve_occupation,
    )

    records = [
        OccupationMarketRecord(
            soc_code="49-9012",
            title="Control and valve installers and repairers, except mechanical door",
        ),
        OccupationMarketRecord(
            soc_code="49-9071",
            title="Maintenance and repair workers, general",
        ),
    ]

    results = resolve_occupation(
        records,
        "Maintenance and repair workers, general",
    )

    assert results
    assert results[0].soc_code == "49-9071"
    assert results[0].confidence == 1.0


def test_onet_skill_match_structure():
    from gvai.postlabor.workers.onet_matcher import OnetSkillMatch

    match = OnetSkillMatch(
        source_code="37-2021.00",
        source_title="Pest Control Workers",
        target_code="49-9071.00",
        target_title="Maintenance and Repair Workers, General",
        skill_transferability=72.5,
        source_skill_count=35,
        target_skill_count=35,
    )

    assert match.skill_transferability == 72.5
    assert match.source_skill_count == 35
    assert match.target_title == "Maintenance and Repair Workers, General"


def test_ai_exposure_category_score():
    from gvai.postlabor.workers.automation_exposure import (
        AIExposureRecord,
        ai_exposure_score,
    )

    low = AIExposureRecord(
        soc_code="A",
        title="Low",
        category="Low",
    )

    very_high = AIExposureRecord(
        soc_code="B",
        title="Very High",
        category="Very high",
    )

    assert ai_exposure_score(low) < ai_exposure_score(very_high)


def test_ai_exposure_with_percentiles():
    from gvai.postlabor.workers.automation_exposure import (
        AIExposureRecord,
        ai_exposure_score,
    )

    record = AIExposureRecord(
        soc_code="A",
        title="Test",
        category="High",
        theoretical_percentile=80,
        observed_percentile=70,
    )

    score = ai_exposure_score(record)

    assert 0 <= score <= 100
    assert score > 60


def test_displacement_separate_from_exposure():
    from gvai.postlabor.workers.automation_exposure import (
        AIExposureRecord,
        assess_automation,
    )

    exposure = AIExposureRecord(
        soc_code="A",
        title="Test Occupation",
        category="Very high",
    )

    growing = assess_automation(
        exposure=exposure,
        employment_change_percent=15,
        physical_task_resilience=80,
        augmentation_potential=80,
    )

    declining = assess_automation(
        exposure=exposure,
        employment_change_percent=-15,
        physical_task_resilience=20,
        augmentation_potential=20,
    )

    assert (
        growing.displacement_pressure
        < declining.displacement_pressure
    )


def test_automation_assessment_bounds():
    from gvai.postlabor.workers.automation_exposure import (
        AIExposureRecord,
        assess_automation,
    )

    exposure = AIExposureRecord(
        soc_code="A",
        title="Test",
        category="Moderate",
    )

    result = assess_automation(
        exposure=exposure,
        employment_change_percent=0,
        physical_task_resilience=50,
        augmentation_potential=50,
    )

    assert 0 <= result.ai_exposure_score <= 100
    assert 0 <= result.displacement_pressure <= 100


def test_onet_characteristics_bounds():
    from gvai.postlabor.workers.onet_characteristics import (
        derive_characteristics,
    )

    result = derive_characteristics(
        occupation_code="TEST",
        title="Test Occupation",
        physical_activity=80,
        worksite_presence=90,
        task_variability=75,
        interpersonal_activity=60,
        information_processing=55,
        routine_activity=30,
    )

    assert 0 <= result.physical_task_resilience <= 100
    assert 0 <= result.augmentation_potential <= 100


def test_physical_work_increases_resilience():
    from gvai.postlabor.workers.onet_characteristics import (
        derive_characteristics,
    )

    physical = derive_characteristics(
        occupation_code="A",
        title="Physical",
        physical_activity=95,
        worksite_presence=95,
        task_variability=80,
        interpersonal_activity=50,
        information_processing=40,
        routine_activity=40,
    )

    desk = derive_characteristics(
        occupation_code="B",
        title="Desk",
        physical_activity=10,
        worksite_presence=20,
        task_variability=50,
        interpersonal_activity=50,
        information_processing=90,
        routine_activity=60,
    )

    assert (
        physical.physical_task_resilience
        > desk.physical_task_resilience
    )


def test_variable_information_work_supports_augmentation():
    from gvai.postlabor.workers.onet_characteristics import (
        derive_characteristics,
    )

    high = derive_characteristics(
        occupation_code="A",
        title="High Augmentation",
        physical_activity=30,
        worksite_presence=40,
        task_variability=90,
        interpersonal_activity=80,
        information_processing=95,
        routine_activity=20,
    )

    low = derive_characteristics(
        occupation_code="B",
        title="Low Augmentation",
        physical_activity=40,
        worksite_presence=50,
        task_variability=20,
        interpersonal_activity=20,
        information_processing=20,
        routine_activity=90,
    )

    assert high.augmentation_potential > low.augmentation_potential


def test_onet_signal_mapper_bounds():
    from gvai.postlabor.sources.onet import (
        OnetWorkActivity,
        OnetWorkContext,
    )
    from gvai.postlabor.workers.onet_signals import build_onet_signals

    activities = [
        OnetWorkActivity(
            element_id="4.A.3.a.1",
            name="Physical",
            description="",
            importance=90,
        ),
        OnetWorkActivity(
            element_id="4.A.2.b.1",
            name="Problem solving",
            description="",
            importance=80,
        ),
        OnetWorkActivity(
            element_id="4.A.2.a.4",
            name="Analyzing",
            description="",
            importance=70,
        ),
    ]

    contexts = [
        OnetWorkContext(
            element_id="4.C.2.d.1.d",
            name="Walking",
            description="",
            context=85,
        ),
        OnetWorkContext(
            element_id="4.C.3.b.7",
            name="Repeating tasks",
            description="",
            context=30,
        ),
    ]

    result = build_onet_signals(activities, contexts)

    assert 0 <= result.physical_activity <= 100
    assert 0 <= result.worksite_presence <= 100
    assert 0 <= result.task_variability <= 100
    assert 0 <= result.interpersonal_activity <= 100
    assert 0 <= result.information_processing <= 100
    assert 0 <= result.routine_activity <= 100
    assert 0 <= result.coverage <= 1


def test_onet_signal_mapper_inverts_repetition_for_variability():
    from gvai.postlabor.sources.onet import OnetWorkContext
    from gvai.postlabor.workers.onet_signals import build_onet_signals

    low_repetition = build_onet_signals(
        [],
        [
            OnetWorkContext(
                element_id="4.C.3.b.7",
                name="Repeating Same Tasks",
                description="",
                context=20,
            )
        ],
    )

    high_repetition = build_onet_signals(
        [],
        [
            OnetWorkContext(
                element_id="4.C.3.b.7",
                name="Repeating Same Tasks",
                description="",
                context=90,
            )
        ],
    )

    assert (
        low_repetition.task_variability
        > high_repetition.task_variability
    )


def test_onet_signal_mapper_ignores_missing_elements():
    from gvai.postlabor.sources.onet import OnetWorkActivity
    from gvai.postlabor.workers.onet_signals import build_onet_signals

    result = build_onet_signals(
        [
            OnetWorkActivity(
                element_id="4.A.3.a.1",
                name="Physical",
                description="",
                importance=80,
            )
        ],
        [],
    )

    assert result.physical_activity == 80.0
    assert result.coverage < 1.0


def test_base_soc_code():
    from gvai.postlabor.workers.occupation_automation import base_soc_code

    assert base_soc_code("37-2021.00") == "37-2021"
    assert base_soc_code("13-2011") == "13-2011"


def test_base_soc_code_strips_whitespace():
    from gvai.postlabor.workers.occupation_automation import base_soc_code

    assert base_soc_code(" 15-1252.00 ") == "15-1252"


def test_onet_code_from_soc():
    from gvai.postlabor.workers.worker_assessment import (
        onet_code_from_soc,
    )

    assert onet_code_from_soc("37-2021") == "37-2021.00"
    assert onet_code_from_soc("15-1252.00") == "15-1252.00"


def test_worker_occupation_resolution_alias():
    from gvai.postlabor.workers.worker_assessment import (
        resolve_worker_occupation,
    )

    result = resolve_worker_occupation("pest tech")

    assert result.candidates
    assert result.candidates[0].soc_code == "37-2021"
    assert result.candidates[0].confidence >= 0.90


def test_worker_occupation_resolution_keeps_ambiguity():
    from gvai.postlabor.workers.worker_assessment import (
        resolve_worker_occupation,
    )

    result = resolve_worker_occupation("warehouse worker")

    assert len(result.candidates) >= 2
    assert result.resolved is False
