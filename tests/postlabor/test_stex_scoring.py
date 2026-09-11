import pytest

from gvai.postlabor.stex import (
    STEX_RUBRIC_VERSION,
    calculate_task_exposure,
)


def test_rubric_version():
    assert STEX_RUBRIC_VERSION == "STEX v0.1"


def test_digital_documentation_example():
    assert calculate_task_exposure(
        digital_capability=4,
        physical_execution=0,
        human_presence_requirement=0,
    ) == 100.0


def test_highly_physical_human_present_example():
    assert calculate_task_exposure(
        digital_capability=0,
        physical_execution=1,
        human_presence_requirement=4,
    ) == 0.0


def test_mixed_task_example():
    assert calculate_task_exposure(
        digital_capability=3,
        physical_execution=1,
        human_presence_requirement=2,
    ) == 37.5


def test_uses_strongest_execution_channel():
    assert calculate_task_exposure(
        digital_capability=1,
        physical_execution=4,
        human_presence_requirement=0,
    ) == 100.0


def test_human_presence_reduces_exposure():
    low_presence = calculate_task_exposure(
        digital_capability=4,
        physical_execution=0,
        human_presence_requirement=1,
    )

    high_presence = calculate_task_exposure(
        digital_capability=4,
        physical_execution=0,
        human_presence_requirement=3,
    )

    assert low_presence == 75.0
    assert high_presence == 25.0
    assert high_presence < low_presence


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("digital_capability", -1),
        ("digital_capability", 5),
        ("physical_execution", -1),
        ("physical_execution", 5),
        ("human_presence_requirement", -1),
        ("human_presence_requirement", 5),
    ],
)
def test_rejects_out_of_range_ratings(field, value):
    kwargs = {
        "digital_capability": 0,
        "physical_execution": 0,
        "human_presence_requirement": 0,
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        calculate_task_exposure(**kwargs)
