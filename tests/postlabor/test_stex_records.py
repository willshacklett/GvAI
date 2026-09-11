import pytest

from gvai.postlabor.stex import TaskRatingRecord


def make_record(**overrides):
    values = {
        "occupation_code": "37-2021.00",
        "occupation_title": "Pest Control Workers",
        "task_id": "7974",
        "task_title": "Record work activities performed.",
        "task_category": "Core",
        "source_importance": 92.0,
        "source_name": "O*NET Tasks / Incumbent",
        "source_year": 2026,
        "digital_capability": 4,
        "physical_execution": 0,
        "human_presence_requirement": 0,
        "augmentation_likelihood": 3,
        "scorer_id": "test-scorer",
        "rationale": "Deterministic test record.",
        "scored_at_utc": "2026-09-11T00:00:00+00:00",
    }
    values.update(overrides)
    return TaskRatingRecord.create(**values)


def test_record_preserves_provenance():
    record = make_record()

    assert record.schema_version == "gvai.stex.task-rating.v0.1"
    assert record.rubric_version == "STEX v0.1"
    assert record.source_year == 2026
    assert record.source_vintage_label == (
        "O*NET Tasks / Incumbent 2026"
    )


def test_record_calculates_exposure():
    record = make_record()

    assert record.structural_exposure == 100.0


def test_new_zero_importance_is_unrated():
    record = make_record(
        task_id="1001584",
        task_title="Monitor inventory of chemicals and supplies.",
        task_category="New",
        source_importance=0.0,
    )

    assert record.importance_status == "unrated"
    assert record.source_importance == 0.0


def test_rated_zero_is_not_silently_reclassified():
    record = make_record(
        task_category="Core",
        source_importance=0.0,
    )

    assert record.importance_status == "rated"


def test_requires_rationale():
    with pytest.raises(ValueError):
        make_record(rationale="   ")


def test_requires_scorer():
    with pytest.raises(ValueError):
        make_record(scorer_id="")


@pytest.mark.parametrize("value", [-1, 5])
def test_rejects_invalid_augmentation(value):
    with pytest.raises(ValueError):
        make_record(augmentation_likelihood=value)


def test_serializes_to_dictionary():
    record = make_record()
    data = record.to_dict()

    assert data["task_id"] == "7974"
    assert data["structural_exposure"] == 100.0
    assert data["rubric_version"] == "STEX v0.1"
