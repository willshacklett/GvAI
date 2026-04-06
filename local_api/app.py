from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="GvAI")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://gvai.io",
        "https://www.gvai.io",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScoreRequest(BaseModel):
    text: str | None = None
    message: str | None = None
    input: str | None = None
    prompt: str | None = None
    series: list[float] | None = None
    tone: str | None = "clean"


ENGINE_AVAILABLE = False
compute_recoverability_signal = None

try:
    from gvai.sentinel import compute_recoverability_signal as _crs
    compute_recoverability_signal = _crs
    ENGINE_AVAILABLE = True
except Exception:
    ENGINE_AVAILABLE = False


def variance_of(values: list[float]) -> float:
    if not values:
        return 0.0
    mean_val = sum(values) / len(values)
    return sum((x - mean_val) ** 2 for x in values) / len(values)


def text_to_series(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        return [0.10, 0.10, 0.10]

    tokens = re.findall(r"[A-Za-z0-9']+|[^\w\s]", text)
    if not tokens:
        tokens = list(text)

    values: list[float] = []
    prev = None

    for tok in tokens:
        if re.fullmatch(r"[^\w\s]", tok):
            base = 0.20
        else:
            length_component = min(len(tok), 12) / 12.0
            vowel_component = sum(1 for c in tok.lower() if c in "aeiou") / max(len(tok), 1)
            upper_component = 0.15 if tok[:1].isupper() else 0.0
            digit_component = 0.12 if any(c.isdigit() for c in tok) else 0.0
            base = 0.18 + 0.55 * length_component + 0.12 * vowel_component + upper_component + digit_component

        if prev is not None:
            delta = abs(base - prev)
            base += min(delta * 0.35, 0.18)

        values.append(round(max(0.05, min(base, 1.95)), 6))
        prev = base

    if len(values) == 1:
        values = [values[0], min(values[0] + 0.02, 1.95), min(values[0] + 0.01, 1.95)]

    return values


def fallback_signal(series: list[float]) -> dict[str, Any]:
    if not series:
        return {
            "score": 0.0,
            "passed": False,
            "fired": False,
            "lead_time": None,
            "mean_step": None,
            "drift_step": None,
            "breach_step": None,
            "collapse_step": None,
            "reasons": ["No signal."],
            "signal": None,
            "timeline": [],
        }

    timeline = []
    breach_step = None
    drift_step = None

    for i in range(len(series)):
        window = series[: i + 1]
        mean_val = sum(window) / len(window)
        variance_val = variance_of(window)
        slope = 0.0 if len(window) < 2 else (window[-1] - window[0]) / max(len(window) - 1, 1)
        drift_confirmed = slope > 0.04 and len(window) >= 4
        variance_breach = variance_val > 0.08

        if breach_step is None and variance_breach:
            breach_step = i
        if drift_step is None and drift_confirmed:
            drift_step = i

        rec = max(0.0, min(1.0, 1.0 - min(variance_val * 2.5 + max(slope, 0.0) * 1.8, 1.0)))
        status = "stable"
        if rec < 0.75:
            status = "warning"
        if rec < 0.50:
            status = "critical"

        delta_t = None
        if rec > 0:
            delta_t = round(60.0 * rec, 3)

        timeline.append({
            "step": i,
            "input_value": window[-1],
            "variance_value": variance_val,
            "variance_breach": variance_breach,
            "drift": {
                "slope": slope,
                "mean": mean_val,
                "variance": variance_val,
                "drift_confirmed": drift_confirmed,
            },
            "load_skew": 0.0,
            "latency_skew": 0.0,
            "recoverability_score": rec,
            "status": status,
            "delta_t_estimate": delta_t,
        })

    last = timeline[-1]
    score_100 = round(float(last["recoverability_score"] or 0.0) * 100.0, 2)
    passed = bool((last["status"] or "").lower() in {"stable", "warning"} and score_100 >= 65.0)
    fired = bool(last["variance_breach"] or last["drift"]["drift_confirmed"])

    reasons = []
    if last["variance_breach"]:
        reasons.append("Variance breach detected.")
    if last["drift"]["drift_confirmed"]:
        reasons.append("Drift confirmation present.")
    if not reasons:
        reasons.append("Signal remains inside the stable boundary.")

    return {
        "score": score_100,
        "passed": passed,
        "fired": fired,
        "lead_time": last["delta_t_estimate"],
        "mean_step": round(sum(series) / len(series), 6),
        "drift_step": drift_step,
        "breach_step": breach_step,
        "collapse_step": None,
        "reasons": reasons,
        "signal": last,
        "timeline": timeline[-10:],
    }


def build_score(series: list[float]) -> dict[str, Any]:
    return fallback_signal(series)


@app.get("/health")
def health():
    return {"ok": True, "engine_available": ENGINE_AVAILABLE}


@app.options("/{path:path}")
def preflight(path: str):
    return {"ok": True}


@app.post("/score")
def score(req: ScoreRequest):
    incoming_text = req.text or req.message or req.input or req.prompt or ""
    tone = req.tone or "clean"
    series = req.series if req.series else text_to_series(incoming_text)
    scored = build_score(series)

    return {
        "ok": True,
        "text": incoming_text,
        "series": series,
        "score": scored["score"],
        "passed": scored["passed"],
        "fired": scored["fired"],
        "lead_time": scored["lead_time"],
        "mean_step": scored["mean_step"],
        "drift_step": scored["drift_step"],
        "breach_step": scored["breach_step"],
        "collapse_step": scored["collapse_step"],
        "tone": tone,
        "reasons": scored["reasons"],
        "signal": scored["signal"],
        "timeline": scored["timeline"],
        "data": {
            "score": scored["score"],
            "passed": scored["passed"],
            "fired": scored["fired"],
            "lead_time": scored["lead_time"],
            "mean_step": scored["mean_step"],
            "drift_step": scored["drift_step"],
            "breach_step": scored["breach_step"],
            "collapse_step": scored["collapse_step"],
            "tone": tone,
            "reasons": scored["reasons"],
            "signal": scored["signal"],
            "timeline": scored["timeline"],
        },
    }


app.mount("/", StaticFiles(directory=".", html=True), name="site")
