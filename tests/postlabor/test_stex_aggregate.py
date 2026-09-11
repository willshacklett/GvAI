import pytest

from gvai.postlabor.stex import (
    TaskRatingRecord,
    aggregate_occupation_stex,
)


def make_record(
    *,
    task_id,
    importance,
    exposure_inputs=(4, 0, 0),
    augmentation=3,
    category="Core",
    occupation_code="37-2021.00",
    occupation_title="Pest Control Workers",
):
    d, p, r = exposure_inputs

    return TaskRatingRecord.create(
        occupation_code=occupation_code,
        occupation_title=occupation_title,
        task_id=task_id,
        task_title=f"Task {task_id}",
        task_category=category,
        source_importance=importance,
        source_name="O*NET Tasks / Incumbent",
        source_year=2026,
        digital_capability=d,
        physical_execution=p,
        human_presence_requirement=r,
        augmentation_likelihood=augmentation,
        scorer_id="test-scorer",
        rationale="Aggregation test.",
        scored_at_utc="2026-09-11T00:00:00+00:00",
    )


def test_weighted_occupation_exposure():
    high = make_record(
        task_id="1",
        importance=80,
        exposure_inputs=(4, 0, 0),
    )

    low = make_record(
        task_id="2",
        importance=20,
        exposure_inputs=(0, 0, 0),
    )

    result = aggregate_occupation_stex([high, low])

    assert result.structural_exposure == 80.0
    assert result.rated_task_count == 2
    assert result.unrated_task_count == 0
    assert result.total_importance_weight == 100.0


def test_unrated_new_task_excluded():
    rated = make_record(
        task_id="1",
        importance=80,
        exposure_inputs=(4, 0, 0),
    )

    new_task = make_record(
        task_id="2",
        importance=0,
        category="New",
        exposure_inputs=(4, 0, 0),
    )

    result = aggregate_occupation_stex(
        [rated, new_task]
    )

    assert result.structural_exposure == 100.0
    assert result.rated_task_count == 1
    assert result.unrated_task_count == 1
    assert result.total_importance_weight == 80.0


def test_weighted_augmentation():
    a = make_record(
        task_id="1",
        importance=75,
        augmentation=4,
    )

    b = make_record(
        task_id="2",
        importance=25,
        augmentation=0,
    )

    result = aggregate_occupation_stex([a, b])

    assert result.augmentation_likelihood == 3.0


def test_rejects_mixed_occupations():
    a = make_record(
        task_id="1",
        importance=50,
    )

    b = make_record(
        task_id="2",
        importance=50,
        occupation_code="99-9999.00",
        occupation_title="Other Occupation",
    )

    with pytest.raises(ValueError):
        aggregate_occupation_stex([a, b])


def test_rejects_empty_input():
    with pytest.raises(ValueError):
        aggregate_occupation_stex([])
