import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

from gvai import adaptive_control as control
import pytest


def _updates(count):
    for attempt in range(count):
        control.update_adaptive_control({"drift_risk": 0.4})


def test_missing_and_corrupt_state_use_independent_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "STATE_PATH", tmp_path / "state.json")
    state = control.load_state()
    state["history"].append({})
    assert control.load_state()["history"] == []
    control.STATE_PATH.write_text("{partial")
    assert control.load_state() == control.DEFAULT


def test_atomic_replace_failure_preserves_previous_state(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(control, "STATE_PATH", tmp_path / "state.json")
    assert control.save_state(control.DEFAULT)
    previous = control.STATE_PATH.read_bytes()

    def fail(*args):
        raise OSError("storage unavailable")

    monkeypatch.setattr(control.os, "replace", fail)
    result = control.update_adaptive_control({"drift_risk": 0.7})
    assert result["persisted"] is False
    assert control.STATE_PATH.read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))
    assert "could not be persisted" in caplog.text


def test_concurrent_threads_preserve_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "STATE_PATH", tmp_path / "state.json")
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_updates, [5] * 8))
    assert len(json.loads(control.STATE_PATH.read_text())["history"]) == 40


def test_concurrent_processes_preserve_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "STATE_PATH", tmp_path / "state.json")
    context = multiprocessing.get_context("fork")
    workers = [context.Process(target=_updates, args=(10,)) for attempt in range(4)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0
    assert len(json.loads(control.STATE_PATH.read_text())["history"]) == 40


def test_history_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(control, "STATE_PATH", tmp_path / "state.json")
    _updates(65)
    assert len(control.load_state()["history"]) == 50


@pytest.mark.parametrize("invalid", [{"last_drift": "bad"}, {"core_ema": "nan"}, {"history": None}])
def test_invalid_state_recovers_without_breaking_updates(tmp_path, monkeypatch, invalid):
    monkeypatch.setattr(control, "STATE_PATH", tmp_path / "state.json")
    control.STATE_PATH.write_text(json.dumps(invalid))
    result = control.update_adaptive_control({"drift_risk": 0.4})
    assert result["persisted"] is True
    assert len(control.load_state()["history"]) == 1


def test_read_only_storage_does_not_break_governance(tmp_path, monkeypatch):
    blocker = tmp_path / "not_a_directory"
    blocker.write_text("occupied")
    monkeypatch.setattr(control, "STATE_PATH", blocker / "state.json")
    result = control.update_adaptive_control({"drift_risk": 0.4})
    assert result["persisted"] is False
    assert result["drift"] == 0.4