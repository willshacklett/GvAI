import json, time
from pathlib import Path

STATE_PATH = Path("data/gv_adaptive_control.json")

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
        return dict(DEFAULT)
    try:
        data = json.loads(STATE_PATH.read_text())
        merged = dict(DEFAULT)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT)

def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["history"] = state.get("history", [])[-50:]
    STATE_PATH.write_text(json.dumps(state, indent=2))

def update_adaptive_control(gv):
    state = load_state()
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
    save_state(state)

    return {
        "control_law": "alpha(t)=alpha_core+k*EMA_fast(delta_drift)",
        "alpha_core": alpha_core,
        "alpha_fast": alpha_fast,
        "k": k,
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
