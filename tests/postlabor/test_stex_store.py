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
