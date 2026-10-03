import fcntl
import json
import logging
import math
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

STATE_PATH = Path(os.getenv("GVAI_ADAPTIVE_CONTROL_PATH", "data/gv_adaptive_control.json"))
_thread_lock = threading.RLock()
logger = logging.getLogger(__name__)

DEFAULT = {
    "last_drift": None,
    "core_ema": 0.0,
    "fast_delta_ema": 0.0,
    "alpha_core": 0.12,
    "alpha_fast": 0.48,
    "k": 0.25,
    "alpha_effective": 0.12,
    "snap_detected": False,
    "history": []
}

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

def load_state():
    if not STATE_PATH.exists():
        return deepcopy(DEFAULT)
    try:
        data = json.loads(STATE_PATH.read_text())
        if not isinstance(data, dict) or not isinstance(data.get("history", []), list):
            raise ValueError("Invalid adaptive control state")
        merged = deepcopy(DEFAULT)
        merged.update(data)
        for field in ("core_ema", "fast_delta_ema", "alpha_core", "alpha_fast", "k", "alpha_effective"):
            if not math.isfinite(float(merged[field])):
                raise ValueError("Non-finite adaptive control state")
        if merged["last_drift"] is not None and not math.isfinite(float(merged["last_drift"])):
            raise ValueError("Invalid previous drift")
        return merged
    except Exception:
        logger.exception("Adaptive control state could not be loaded")
        return deepcopy(DEFAULT)


@contextmanager
def _state_lock():
    with _thread_lock:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with STATE_PATH.with_suffix(".lock").open("a") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)


def _save_state(state):
    temporary_path = None
    try:
        bounded_state = {**state, "history": state.get("history", [])[-50:]}
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=STATE_PATH.parent,
            prefix=f".{STATE_PATH.name}.", suffix=".tmp", delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(bounded_state, temporary, indent=2, allow_nan=False)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, STATE_PATH)
        return True
    except (OSError, TypeError, ValueError):
        logger.exception("Adaptive control state could not be persisted")
        return False
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

def save_state(state):
    try:
        with _state_lock():
            return _save_state(state)
    except OSError:
        logger.exception("Adaptive control storage is unavailable")
        return False

def update_adaptive_control(gv):
    try:
        with _state_lock():
            return _update_state(load_state(), gv)
    except OSError:
        logger.exception("Adaptive control storage is unavailable; using transient state")
        return _update_state(load_state(), gv, persist=False)


def _update_state(state, gv, persist=True):
    drift = float(gv.get("drift_risk", 0.0) or 0.0)
    prev = state.get("last_drift")
    delta = 0.0 if prev is None else drift - float(prev)

    alpha_core = float(state["alpha_core"])
    alpha_fast = float(state["alpha_fast"])
    k = float(state["k"])

    core = alpha_core * drift + (1 - alpha_core) * float(state["core_ema"])
    fast = alpha_fast * max(0.0, delta) + (1 - alpha_fast) * float(state["fast_delta_ema"])

    alpha_effective = clamp(alpha_core + k * fast, 0.05, 0.85)
    alpha_jump = abs(alpha_effective - float(state["alpha_effective"]))
    snap = alpha_jump > 0.20

    event = {
        "timestamp": time.time(),
        "drift": round(drift, 3),
        "delta_drift": round(delta, 3),
        "core_ema": round(core, 3),
        "fast_delta_ema": round(fast, 3),
        "alpha_effective": round(alpha_effective, 3),
        "alpha_jump": round(alpha_jump, 3),
        "snap_detected": snap
    }

    state.update({
        "last_drift": drift,
        "core_ema": core,
        "fast_delta_ema": fast,
        "alpha_effective": alpha_effective,
        "snap_detected": snap
    })
    state.setdefault("history", []).append(event)
    persisted = _save_state(state) if persist else False

    return {
        "control_law": "alpha(t)=alpha_core+k*EMA_fast(delta_drift)",
        "alpha_core": alpha_core,
        "alpha_fast": alpha_fast,
        "k": k,
        "persisted": persisted,
        **event
    }

def get_adaptive_control_state():
    state = load_state()
    return {
        "ok": True,
        "control_law": "alpha(t)=alpha_core+k*EMA_fast(delta_drift)",
        "alpha_core": state["alpha_core"],
        "alpha_fast": state["alpha_fast"],
        "k": state["k"],
        "alpha_effective": round(float(state["alpha_effective"]), 3),
        "core_ema": round(float(state["core_ema"]), 3),
        "fast_delta_ema": round(float(state["fast_delta_ema"]), 3),
        "snap_detected": state["snap_detected"],
        "history": state.get("history", [])[-10:]
    }
