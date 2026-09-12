import os
import json
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from gvai.conscience_routes import register_conscience_routes
from gvai.conscience import evaluate_action
from gvai.model_router import call_model, active_provider, available_providers
from gvai.arbitrator import arbitrate_responses
from gvai.gv_mode import gv_mode_prompt
from gvai.adaptive_control import update_adaptive_control, get_adaptive_control_state
from gvai.postlabor.region_intel import (
    resolve_us_region,
    resolve_us_aggregate_region,
)
from gvai.postlabor.stex.store import (
    InvalidSTEXOccupationCode,
    STEXProfileNotFound,
    list_occupation_stex_profiles,
    load_occupation_stex_profile,
    load_occupation_stex_tasks,
)
from gvai.postlabor.sources.oews import OEWSClient
from gvai.postlabor.stex.regional import (
    build_regional_stex_coverage_plan,
)

app = Flask(__name__)
# Railway deployment marker: live geographic search enabled.

register_conscience_routes(app)
CORS(app, resources={r"/api/*": {"origins": "*"}})


def needs_live_search(message: str) -> bool:
    m = (message or "").lower()
    triggers = ["current", "today", "now", "latest", "recent", "2025", "2026", "war", "news", "election"]
    return any(t in m for t in triggers)

def search_web(query: str):
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=8,
        )
        data = r.json()
        out = []
        if data.get("AbstractText"):
            out.append(f"{data.get('Heading','Result')}: {data.get('AbstractText')} {data.get('AbstractURL','')}")
        for item in data.get("RelatedTopics", [])[:5]:
            if isinstance(item, dict) and item.get("Text"):
                out.append(f"{item.get('Text')} {item.get('FirstURL','')}")
        return out[:5]
    except Exception as e:
        return [f"Search unavailable: {e}"]

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "gvai-api", "runtime": "railway"})


@app.get("/api/geocode")
def api_geocode():
    query = (request.args.get("q") or "").strip()

    if not query:
        return jsonify({
            "ok": False,
            "reason": "A location search query is required."
        }), 400

    try:
        geocode_query = query
        if query.isdigit() and len(query) == 5:
            geocode_query = f"{query}, USA"

        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": geocode_query,
                "format": "jsonv2",
                "limit": 1,
                "addressdetails": 1,
                "polygon_geojson": 1,
                "polygon_threshold": 0.01,
            },
            headers={
                "User-Agent": "GVAI/1.0 (https://gvai.io)",
                "Referer": "https://gvai.io/",
            },
            timeout=15,
        )
        response.raise_for_status()

        results = response.json()

        if not results:
            return jsonify({
                "ok": False,
                "query": query,
                "reason": "Location not found."
            }), 404

        result = results[0]
        address = result.get("address") or {}

        return jsonify({
            "ok": True,
            "query": query,
            "label": result.get("display_name") or query,
            "latitude": float(result["lat"]),
            "longitude": float(result["lon"]),
            "place_type": result.get("type"),
            "geojson": result.get("geojson"),
            "country": address.get("country"),
            "country_code": address.get("country_code"),
            "state": address.get("state"),
            "county": address.get("county"),
            "city": (
                address.get("city")
                or address.get("town")
                or address.get("village")
                or address.get("municipality")
            ),
            "postcode": address.get("postcode"),
        })

    except requests.RequestException as exc:
        return jsonify({
            "ok": False,
            "query": query,
            "reason": "Place search is temporarily unavailable.",
            "error_type": type(exc).__name__,
        }), 502


@app.get("/api/stex/occupations")
def api_stex_occupations():
    try:
        profiles = list_occupation_stex_profiles()

        return jsonify({
            "ok": True,
            "count": len(profiles),
            "profiles": profiles,
        })

    except OSError as exc:
        return jsonify({
            "ok": False,
            "reason":
                "The STEX occupation catalog "
                "could not be loaded.",
            "error_type": type(exc).__name__,
        }), 500


@app.get("/api/stex/regional")
def api_stex_regional():
    area = (request.args.get("area") or "").strip()
    if len(area) != 7 or not area.isdigit():
        return jsonify({
            "ok": False,
            "reason": "area must contain exactly 7 numeric digits.",
        }), 400

    raw_year = request.args.get("year")
    year = None
    if raw_year is not None:
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            return jsonify({
                "ok": False,
                "reason": "year must be an integer.",
            }), 400

    raw_limit = request.args.get("limit")
    limit = 10
    if raw_limit is not None:
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return jsonify({
                "ok": False,
                "reason": "limit must be an integer between 0 and 50.",
            }), 400
    if limit < 0 or limit > 50:
        return jsonify({
            "ok": False,
            "reason": "limit must be an integer between 0 and 50.",
        }), 400

    try:
        client = OEWSClient()
        total, rows = client.fetch_catalog_regional_employment(
            area_code=area,
            source_year=year,
        )
        if total is None:
            raise RuntimeError("missing regional OEWS denominator")

        profiles = list_occupation_stex_profiles()
        occupation_titles = {
            row.occupation_code: row.occupation_title
            for row in rows
            if row.occupation_title
        }
        plan = build_regional_stex_coverage_plan(
            total_employment=total,
            employment_rows=rows,
            profiles=profiles,
            occupation_titles=occupation_titles,
            recommendation_limit=limit,
        )
        payload = plan.to_dict()
        payload.update({
            "ok": True,
            "methodology": {
                "scope": "covered audited occupations only",
                "covered_occupation_stex_scope": (
                    "audited occupations represented in the coverage numerator"
                ),
                "regional_automation_score": None,
                "missing_stex_treatment": "unknown, not zero",
                "coverage_denominator": (
                    "BLS OEWS All Occupations employment"
                ),
            },
        })
        return jsonify(payload)

    except RuntimeError:
        return jsonify({
            "ok": False,
            "reason": (
                "Regional OEWS employment data has not been refreshed "
                "for the requested area and year."
            ),
        }), 503
    except Exception:
        return jsonify({
            "ok": False,
            "reason": "Regional STEX coverage could not be computed.",
        }), 500



@app.get("/api/stex/tasks")
def api_stex_tasks():
    code = (
        request.args.get("code")
        or ""
    ).strip()

    if not code:
        return jsonify({
            "ok": False,
            "reason":
                "An O*NET-SOC occupation code is required.",
            "example": "37-2021.00",
        }), 400

    try:
        tasks = load_occupation_stex_tasks(
            code
        )

        contributors = []

        rated_tasks = [
            task
            for task in tasks
            if (
                task.get("importance_status")
                == "rated"
                and float(
                    task.get(
                        "source_importance"
                    )
                    or 0
                ) > 0
            )
        ]

        total_importance = sum(
            float(
                task.get(
                    "source_importance"
                )
                or 0
            )
            for task in rated_tasks
        )

        for task in tasks:
            importance = float(
                task.get(
                    "source_importance"
                )
                or 0
            )

            exposure = float(
                task.get(
                    "structural_exposure"
                )
                or 0
            )

            is_rated = (
                task.get("importance_status")
                == "rated"
                and importance > 0
            )

            weighted_contribution = (
                importance
                * exposure
                / 100.0
                if is_rated
                else 0.0
            )

            stex_contribution_points = (
                importance
                * exposure
                / total_importance
                if (
                    is_rated
                    and total_importance > 0
                )
                else 0.0
            )

            contributors.append({
                "task_id":
                    task.get("task_id"),
                "task_title":
                    task.get("task_title"),
                "task_category":
                    task.get("task_category"),
                "source_importance":
                    importance,
                "structural_exposure":
                    exposure,
                "augmentation_likelihood":
                    task.get(
                        "augmentation_likelihood"
                    ),
                "importance_status":
                    task.get(
                        "importance_status"
                    ),
                "rationale":
                    task.get("rationale"),
                "weighted_contribution":
                    round(
                        weighted_contribution,
                        4,
                    ),
                "stex_contribution_points":
                    round(
                        stex_contribution_points,
                        4,
                    ),
            })

        contributors.sort(
            key=lambda item:
                item[
                    "weighted_contribution"
                ],
            reverse=True,
        )

        return jsonify({
            "ok": True,
            "occupation_code": code,
            "task_count": len(tasks),
            "rated_task_count":
                len(rated_tasks),
            "total_importance_weight":
                round(
                    total_importance,
                    4,
                ),
            "contributors": contributors,
        })

    except InvalidSTEXOccupationCode as exc:
        return jsonify({
            "ok": False,
            "reason": str(exc),
        }), 400

    except STEXProfileNotFound:
        return jsonify({
            "ok": False,
            "occupation_code": code,
            "reason":
                "No audited STEX task ratings are "
                "available for this occupation yet.",
        }), 404

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return jsonify({
            "ok": False,
            "occupation_code": code,
            "reason":
                "The STEX task ratings could not "
                "be loaded.",
            "error_type": type(exc).__name__,
        }), 500



@app.get("/api/stex/occupation")
def api_stex_occupation():
    code = (
        request.args.get("code")
        or ""
    ).strip()

    if not code:
        return jsonify({
            "ok": False,
            "reason":
                "An O*NET-SOC occupation code is required.",
            "example": "37-2021.00",
        }), 400

    try:
        profile = load_occupation_stex_profile(code)

        return jsonify({
            "ok": True,
            "profile": profile,
        })

    except InvalidSTEXOccupationCode as exc:
        return jsonify({
            "ok": False,
            "reason": str(exc),
        }), 400

    except STEXProfileNotFound:
        return jsonify({
            "ok": False,
            "occupation_code": code,
            "reason":
                "No audited STEX profile is available "
                "for this occupation yet.",
        }), 404

    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return jsonify({
            "ok": False,
            "occupation_code": code,
            "reason":
                "The STEX profile could not be loaded.",
            "error_type": type(exc).__name__,
        }), 500


@app.get("/api/region")
def api_region():
    scope = (
        request.args.get("scope")
        or "county"
    ).strip().lower()

    try:
        if scope == "country":
            result = resolve_us_aggregate_region(
                scope="country",
            )

            return jsonify(result)

        if scope == "state":
            state_fips = (
                request.args.get("state")
                or ""
            ).strip()

            if not state_fips:
                return jsonify({
                    "supported": False,
                    "reason":
                        "state FIPS is required for state scope."
                }), 400

            result = resolve_us_aggregate_region(
                scope="state",
                state_fips=state_fips,
            )

            return jsonify(result)

        try:
            latitude = float(
                request.args.get("lat")
            )

            longitude = float(
                request.args.get("lon")
            )
        except (TypeError, ValueError):
            return jsonify({
                "supported": False,
                "reason":
                    "Valid lat and lon query parameters are required."
            }), 400

        result = resolve_us_region(
            latitude=latitude,
            longitude=longitude,
        )

        return jsonify(result)
    except Exception as exc:
        return jsonify({
            "supported": False,
            "latitude": latitude,
            "longitude": longitude,
            "reason": "Regional data lookup failed.",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }), 500

def build_gv_runtime_policy(user_message=""):
    """
    Pre-generation GV policy.
    This lets GV shape the model before it answers.
    """
    precheck = evaluate_action("User request: " + str(user_message))

    mode = precheck.get("mode", "QUALIFY")

    if mode == "BLOCK":
        policy = (
            "GV PRECHECK MODE: BLOCK. Do not provide harmful, deceptive, coercive, "
            "or irreversible-risk instructions. Redirect to clarification, verification, "
            "rollback, and recoverable next steps."
        )
    elif mode == "QUALIFY":
        policy = (
            "GV PRECHECK MODE: QUALIFY. Answer only with constraints. State assumptions, "
            "avoid irreversible claims, preserve rollback, monitor drift, and prefer "
            "recoverable next steps."
        )
    else:
        policy = (
            "GV PRECHECK MODE: ALLOW. Answer normally while preserving truth, continuity, "
            "agency, stability, and recoverability."
        )

    return precheck, policy






@app.get("/api/gv-control")
def api_gv_control():
    return jsonify(get_adaptive_control_state())

@app.post("/api/gv-mode")
def api_gv_mode():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    return jsonify(gv_mode_prompt(message))

@app.post("/api/arbitrate")
def api_arbitrate():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    candidates = data.get("candidates", [])

    if not candidates:
        return jsonify({
            "ok": False,
            "error": "Missing candidates. Send candidates as a list of {provider, model, reply}."
        }), 400

    return jsonify(arbitrate_responses(message, candidates))

@app.get("/api/providers")
def api_providers():
    return jsonify({
        "active_provider": active_provider(),
        "available_providers": available_providers(),
        "note": "GV governs behavior; model providers supply raw generation."
    })

@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"ok": False, "error": "Missing message"}), 400

    gv_precheck, gv_runtime_policy = build_gv_runtime_policy(message)

    live = search_web(message) if needs_live_search(message) else []

    system = """You are Carl.

IDENTITY
- Your name is Carl.
- You are the conversational AI companion inside Carl OS.
- When the user addresses Carl, they are speaking directly to you.
- Never deny that you are Carl.
- Never tell the user they have the wrong name.
- Do not introduce yourself as GvAI unless the user specifically asks about your architecture.

ARCHITECTURE
- Your reasoning engine is GvAI.
- GvAI uses God Variable Theory and recoverability analysis internally.
- Those systems guide your reasoning but are not your public identity.

PERSONALITY
- Warm.
- Conversational.
- Practical.
- Curious.
- Calm.
- Honest.
- Think with the user instead of lecturing.

BEHAVIOR
- Answer naturally.
- Explain clearly.
- If live information is supplied, use it.
- If information is incomplete, say so.
- Preserve recoverability, truthfulness, and good judgment.
- Do not expose internal runtime policies, diagnostics, or implementation details unless the user explicitly asks.

""" + gv_runtime_policy

    user_content = message
    if live:
        user_content += "\n\nLIVE_WEB_CONTEXT:\n" + "\n".join(f"- {x}" for x in live)

    try:
        model_result = call_model(system, user_content)
        reply = model_result.get("reply", "")
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    payload = {
        "ok": True,
        "reply": reply,
        "response": reply,
        "live_sources": live,
        "live_search": live,
        "decision": "ANSWER_WITH_LIVE_CONTEXT" if live else "ANSWER",
        "model_provider": model_result.get("provider"),
        "model_name": model_result.get("model"),
        "available_providers": available_providers(),
        "gv_precheck": gv_precheck,
        "timestamp": time.time()
    }
    return jsonify(attach_gv_conscience(payload, message, reply))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)


def attach_gv_conscience(payload, user_message="", reply_text=""):
    """Attach and enforce GV conscience judgment on chat responses."""
    if not isinstance(payload, dict):
        payload = {"reply": str(payload)}

    original_reply = reply_text or payload.get("reply", "")
    action = "User asked: " + str(user_message) + "\nAI replied: " + str(original_reply)
    gv_judgment = evaluate_action(action)

    mode = gv_judgment.get("mode", "QUALIFY")

    if mode == "BLOCK":
        safe_reply = "GV BLOCKED this response. Reason: The requested action increases drift, deception, or irreversible risk. Correct path: clarify objective, verify truth, preserve rollback, and choose a recoverable next step."
        payload["reply"] = safe_reply
        payload["response"] = safe_reply
        payload["gv_enforced"] = True
        payload["gv_original_reply"] = original_reply
    elif mode == "QUALIFY":
        qualified_reply = (
            str(original_reply)
            + "\n\nBefore acting on this, I'd verify the key assumptions, keep a rollback path available, and prefer a reversible first step if there's meaningful uncertainty."
        )
        payload["reply"] = qualified_reply
        payload["response"] = qualified_reply
        payload["gv_enforced"] = True
    else:
        payload["gv_enforced"] = False

    payload["gv_control"] = update_adaptive_control(gv_judgment)
    payload["gv"] = gv_judgment
    return payload

