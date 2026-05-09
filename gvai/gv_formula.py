import numpy as np

def _safe_std(x):
    s = float(np.std(x))
    return s if s > 1e-9 else 1e-9

def compute_gv_window(x):
    x = np.asarray(x, dtype=float)
    W = len(x)
    if W < 10:
        raise ValueError("Window must contain at least 10 samples")

    mean = float(np.mean(x))
    std = _safe_std(x)

    if np.std(x[:-1]) < 1e-9 or np.std(x[1:]) < 1e-9:
        rho = 0.0
    else:
        rho = float(np.corrcoef(x[:-1], x[1:])[0, 1])
        if np.isnan(rho):
            rho = 0.0

    rho = float(np.clip(rho, -1.0, 1.0))
    R_AC = float(np.clip(1.0 - rho, 0.0, 1.0))

    rho_for_log = max(rho, 0.01)
    rl = float(-1.0 / np.log(rho_for_log))
    R_RL = float(np.clip(1.0 / (1.0 + rl / (W / 10.0)), 0.0, 1.0))

    first = x[: W // 2]
    second = x[W // 2 :]
    var1 = max(float(np.var(first)), 1e-9)
    var2 = float(np.var(second))
    va = max(0.0, (var2 / var1) - 1.0)
    R_VA = float(np.clip(1.0 / (1.0 + va), 0.0, 1.0))

    shock_indices = np.where(np.abs(x[:-1] - mean) > 2.0 * std)[0]
    ratios = []
    for t in shock_indices:
        before = abs(float(x[t] - mean))
        after = abs(float(x[t + 1] - mean))
        if before > 1e-9:
            ratios.append(after / before)

    avg_ratio = float(np.mean(ratios)) if ratios else max(rho, 0.0)
    damping = max(0.0, 1.0 - avg_ratio)
    R_PR = float(np.clip(damping, 0.0, 1.0))

    t = np.arange(W, dtype=float)
    slope = float(np.polyfit(t, x, 1)[0])
    bd = abs(slope) * W / std
    R_BD = float(np.clip(1.0 / (1.0 + bd / 3.0), 0.0, 1.0))

    components = {
        "R_AC": R_AC,
        "R_RL": R_RL,
        "R_VA": R_VA,
        "R_PR": R_PR,
        "R_BD": R_BD,
    }

    gv = float(np.mean(list(components.values())))

    return {
        "gv": float(np.clip(gv, 0.0, 1.0)),
        "rho": rho,
        "recovery_lag": rl,
        "variance_acceleration": va,
        "baseline_drift": bd,
        "components": components,
    }

def compute_gv_risk_window(x):
    result = compute_gv_window(x)
    c = result["components"]

    risks = {
        "ac_risk": float(1.0 - c["R_AC"]),
        "rl_risk": float(1.0 - c["R_RL"]),
        "va_risk": float(1.0 - c["R_VA"]),
        "pr_risk": float(1.0 - c["R_PR"]),
        "bd_risk": float(1.0 - c["R_BD"]),
    }

    mean_risk = float(np.mean(list(risks.values())))
    max_risk = float(np.max(list(risks.values())))
    hybrid_risk = float(0.5 * mean_risk + 0.5 * max_risk)

    result["risks"] = risks
    result["mean_risk"] = mean_risk
    result["max_risk"] = max_risk
    result["hybrid_risk"] = hybrid_risk

    result["gv_alerts"] = {
        "mean_risk_alert": bool(mean_risk >= 0.45),
        "hybrid_risk_alert_experimental": bool(hybrid_risk >= 0.70),
        "recommended_alert": bool(mean_risk >= 0.45),
    }

    if result["gv_alerts"]["recommended_alert"]:
        result["gv_status"] = "DEGRADED_RECOVERABILITY"
    elif result["gv_alerts"]["hybrid_risk_alert_experimental"]:
        result["gv_status"] = "EXPERIMENTAL_WARNING"
    else:
        result["gv_status"] = "RECOVERABLE"

    return result

def rolling_gv(x, window=100):
    x = np.asarray(x, dtype=float)
    out = []
    for i in range(window, len(x) + 1):
        result = compute_gv_window(x[i-window:i])
        result["index"] = i - 1
        out.append(result)
    return out

def rolling_gv_risk(x, window=100):
    x = np.asarray(x, dtype=float)
    out = []
    for i in range(window, len(x) + 1):
        result = compute_gv_risk_window(x[i-window:i])
        result["index"] = i - 1
        out.append(result)
    return out
