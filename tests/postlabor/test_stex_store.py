import json

import pytest

from gvai.postlabor.stex.store import (
    InvalidSTEXOccupationCode,
    STEXProfileNotFound,
    load_occupation_stex_profile,
    normalize_occupation_code,
    occupation_profile_path,
)


def test_normalize_valid_onet_soc_code():
    assert (
        normalize_occupation_code(" 37-2021.00 ")
        == "37-2021.00"
    )


@pytest.mark.parametrize(
    "code",
    [
        "",
        "37-2021",
        "372021",
        "../37-2021.00",
        "37-2021.000",
    ],
)
def test_rejects_invalid_occupation_code(code):
    with pytest.raises(InvalidSTEXOccupationCode):
        normalize_occupation_code(code)


def test_profile_path_uses_safe_filename(tmp_path):
    path = occupation_profile_path(
        "37-2021.00",
        data_root=tmp_path,
    )

    assert path == tmp_path / "37-2021_00.stex.json"


def test_load_profile(tmp_path):
    payload = {
        "occupation_code": "37-2021.00",
        "occupation_title": "Pest Control Workers",
        "structural_exposure": 35.6614,
        "rubric_version": "STEX v0.1",
    }

    path = tmp_path / "37-2021_00.stex.json"
    path.write_text(json.dumps(payload))

    result = load_occupation_stex_profile(
        "37-2021.00",
        data_root=tmp_path,
    )

    assert result == payload


def test_missing_profile_raises(tmp_path):
    with pytest.raises(STEXProfileNotFound):
        load_occupation_stex_profile(
            "37-2021.00",
            data_root=tmp_path,
        )


def test_rejects_mismatched_profile(tmp_path):
    path = tmp_path / "37-2021_00.stex.json"

    path.write_text(
        json.dumps({
            "occupation_code": "11-1011.00",
        })
    )

    with pytest.raises(ValueError):
        load_occupation_stex_profile(
            "37-2021.00",
            data_root=tmp_path,
        )



def test_list_occupation_stex_profiles(tmp_path):
    from gvai.postlabor.stex.store import (
        list_occupation_stex_profiles,
    )

    (tmp_path / "37-2021_00.stex.json").write_text(
        json.dumps({
            "occupation_code": "37-2021.00",
            "occupation_title": "Pest Control Workers",
            "structural_exposure": 35.6614,
            "augmentation_likelihood": 2.4624,
            "rated_task_count": 14,
            "unrated_task_count": 1,
            "rubric_version": "STEX v0.1",
            "source": {
                "name": "O*NET Web Services",
                "tasks_year": 2026,
            },
        })
    )

    profiles = list_occupation_stex_profiles(
        data_root=tmp_path
    )

    assert len(profiles) == 1
    assert (
        profiles[0]["occupation_code"]
        == "37-2021.00"
    )
    assert (
        profiles[0]["occupation_title"]
        == "Pest Control Workers"
    )
    assert (
        profiles[0]["structural_exposure"]
        == 35.6614
    )


def test_list_occupation_stex_profiles_empty(tmp_path):
    from gvai.postlabor.stex.store import (
        list_occupation_stex_profiles,
    )

    profiles = list_occupation_stex_profiles(
        data_root=tmp_path
    )

    assert profiles == []


def test_list_occupation_stex_profiles_skips_bad_files(
    tmp_path,
):
    from gvai.postlabor.stex.store import (
        list_occupation_stex_profiles,
    )

    (tmp_path / "broken.stex.json").write_text(
        "{not valid json"
    )

    (tmp_path / "bad-code.stex.json").write_text(
        json.dumps({
            "occupation_code": "../../etc/passwd",
            "occupation_title": "Bad",
        })
    )

    profiles = list_occupation_stex_profiles(
        data_root=tmp_path
    )

    assert profiles == []



def test_load_occupation_stex_tasks(
    tmp_path,
):
    from gvai.postlabor.stex.store import (
        load_occupation_stex_tasks,
    )

    occupation_dir = (
        tmp_path / "37-2021_00"
    )

    occupation_dir.mkdir()

    (occupation_dir / "1.json").write_text(
        json.dumps({
            "occupation_code":
                "37-2021.00",
            "task_id": "1",
            "source_importance": 40,
            "structural_exposure": 50,
        })
    )

    (occupation_dir / "2.json").write_text(
        json.dumps({
            "occupation_code":
                "37-2021.00",
            "task_id": "2",
            "source_importance": 90,
            "structural_exposure": 25,
        })
    )

    tasks = load_occupation_stex_tasks(
        "37-2021.00",
        data_root=tmp_path,
    )

    assert len(tasks) == 2
    assert tasks[0]["task_id"] == "2"
    assert tasks[1]["task_id"] == "1"


def test_load_occupation_stex_tasks_missing(
    tmp_path,
):
    from gvai.postlabor.stex.store import (
        STEXProfileNotFound,
        load_occupation_stex_tasks,
    )

    import pytest

    with pytest.raises(
        STEXProfileNotFound
    ):
        load_occupation_stex_tasks(
            "37-2021.00",
            data_root=tmp_path,
        )


def test_load_occupation_stex_tasks_rejects_bad_code(
    tmp_path,
):
    from gvai.postlabor.stex.store import (
        InvalidSTEXOccupationCode,
        load_occupation_stex_tasks,
    )

    import pytest

    with pytest.raises(
        InvalidSTEXOccupationCode
    ):
        load_occupation_stex_tasks(
            "../../etc/passwd",
            data_root=tmp_path,
        )
