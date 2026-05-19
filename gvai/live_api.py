from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path

from gvai.grounding import grounding_packet, search_knowledge, rebuild_index
from gvai.web_search import search_web
from gvai.conscience import evaluate_action, gv_conscience_statement
from gvai.conscience_routes import register_conscience_routes
from gvai.kernel.runtime import score_runtime
from gvai.kernel.trajectory import load_state, reset_state, update_state
from gvai.kernel.intervention import decide_intervention
from gvai.kernel.arbitration import arbitrate
from gvai.kernel.orchestrator import run_kernel
from gvai.kernel.observatory import observatory_snapshot
from gvai.kernel.protocol import build_gv_heartbeat, validate_heartbeat
from gvai.kernel.phase_timeline import load_timeline, reset_timeline, update_timeline
from gvai.kernel.phase_lock import detect_phase_lock

app = Flask(__name__, static_folder="../web", static_url_path="")

register_conscience_routes(app)
CORS(app)

@app.get("/")
def root():
    if Path("web/index.html").exists():
        return send_from_directory("web", "index.html")
    return jsonify({"ok": True, "runtime": "railway", "service": "gvai-api"})

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "runtime": "railway", "service": "gvai-api"})

@app.get("/api/grounding/search")
def grounding_search():
    q = request.args.get("q", "")
    return jsonify({"ok": True, "query": q, "hits": search_knowledge(q)})

@app.post("/api/grounding/rebuild")
def grounding_rebuild():
    return jsonify(rebuild_index())

def needs_web(msg: str) -> bool:
    m = (msg or "").lower()
    return any(k in m for k in [
        "weather", "today", "now", "current", "latest", "news",
        "score", "stock", "price", "live", "this weekend"
    ])

@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    msg = data.get("message") or data.get("input") or ""
    if not isinstance(msg, str):
        msg = str(msg)

    if needs_web(msg):
        web = search_web(msg)
        answer = f"🌐 I looked that up for you:\n{web.get('result', 'web search failed')}"
        return jsonify({
            "ok": True,
            "reply": answer,
            "response": answer,
            "web": web,
            "grounded": False,
            "sources": [],
            "input": msg
        })

    gp = grounding_packet(msg)

    system = (
        "You are GvAI, a survivability-first intelligence system.\n"
        "Use the grounded context first. Do not invent facts outside it.\n\n"
        + gp["context"]
    ) if gp["grounded"] else "You are GvAI. No grounding context found. Be honest."

    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": msg}
            ],
            temperature=0.35,
        )
        answer = resp.choices[0].message.content
    except Exception as e:
        answer = f"[MODEL ERROR] {e}"

    return jsonify({
        "ok": True,
        "response": answer,
        "reply": answer,
        "grounded": gp["grounded"],
        "sources": gp["sources"],
        "input": msg
    })



# --- GV CONSCIENCE ROUTES ---
@app.route("/api/conscience", methods=["GET"], endpoint="api_conscience_statement_get")
def api_conscience_statement():
    return jsonify(gv_conscience_statement())

@app.route("/api/conscience/evaluate", methods=["POST"], endpoint="api_conscience_evaluate_post")
def api_conscience_evaluate():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action", "")
    context = payload.get("context", "")
    return jsonify(evaluate_action(action, context))
# --- END GV CONSCIENCE ROUTES ---


@app.route("/api/kernel/score", methods=["GET", "POST"], endpoint="api_kernel_score")
def api_kernel_score():
    if request.method == "GET":
        return jsonify({
            "ok": True,
            "endpoint": "/api/kernel/score",
            "method": "POST",
            "purpose": "GV kernel runtime scoring"
        })

    data = request.get_json(silent=True) or {}
    return jsonify(score_runtime(
        user_message=data.get("user_message", ""),
        candidate_response=data.get("candidate_response", ""),
        context=data.get("context", "api-kernel-score")
    ))


@app.route("/api/kernel/trajectory", methods=["GET", "POST"], endpoint="api_kernel_trajectory")
def api_kernel_trajectory():
    if request.method == "GET":
        return jsonify(load_state())

    data = request.get_json(silent=True) or {}

    if data.get("reset") is True:
        return jsonify(reset_state())

    runtime_payload = data.get("runtime") or data.get("gv_runtime") or {}
    label = data.get("label", "api-kernel-trajectory")

    return jsonify(update_state(runtime_payload, label=label))


@app.route("/api/kernel/intervention", methods=["GET", "POST"], endpoint="api_kernel_intervention")
def api_kernel_intervention():
    if request.method == "GET":
        return jsonify(decide_intervention(load_state()))

    data = request.get_json(silent=True) or {}
    state = data.get("state") or load_state()
    return jsonify(decide_intervention(state))


@app.route("/api/kernel/arbitrate", methods=["POST"], endpoint="api_kernel_arbitrate")
def api_kernel_arbitrate():
    data = request.get_json(silent=True) or {}
    return jsonify(arbitrate(
        user_message=data.get("user_message", ""),
        candidates=data.get("candidates", []),
        context=data.get("context", "api-kernel-arbitrate")
    ))


@app.route("/api/kernel/run", methods=["POST"], endpoint="api_kernel_run")
def api_kernel_run():
    data = request.get_json(silent=True) or {}
    return jsonify(run_kernel(
        user_message=data.get("user_message", ""),
        candidate_response=data.get("candidate_response", ""),
        candidates=data.get("candidates", []),
        context=data.get("context", "api-kernel-run")
    ))


@app.route("/api/kernel/observatory", methods=["GET"], endpoint="api_kernel_observatory")
def api_kernel_observatory():
    return jsonify(observatory_snapshot())



@app.route("/dashboard/gv-kernel-observatory/")
def gv_kernel_observatory():
    return send_from_directory(
        "dashboard/gv-kernel-observatory",
        "index.html"
    )

@app.route("/dashboard/gv-kernel-observatory/<path:path>")
def gv_kernel_observatory_assets(path):
    return send_from_directory(
        "dashboard/gv-kernel-observatory",
        path
    )




@app.route(
    "/api/kernel/heartbeat",
    methods=["GET", "POST"],
    endpoint="api_kernel_heartbeat"
)
def api_kernel_heartbeat():

    if request.method == "GET":
        payload = build_gv_heartbeat(
            context="heartbeat-empty"
        )

        return jsonify(payload)

    data = request.get_json(silent=True) or {}

    payload = build_gv_heartbeat(
        runtime=data.get("runtime", {}),
        debt=data.get("debt", {}),
        phase=data.get("phase", {}),
        visible_coherence=data.get("visible_coherence"),
        context=data.get(
            "context",
            "heartbeat-runtime"
        ),
    )

    return jsonify(payload)


@app.route(
    "/api/kernel/heartbeat/validate",
    methods=["POST"],
    endpoint="api_kernel_heartbeat_validate"
)
def api_kernel_heartbeat_validate():

    data = request.get_json(silent=True) or {}

    return jsonify(validate_heartbeat(data))



@app.route("/api/kernel/phase/timeline", methods=["GET", "POST"], endpoint="api_kernel_phase_timeline")
def api_kernel_phase_timeline():

    if request.method == "GET":
        return jsonify(load_timeline())

    data = request.get_json(silent=True) or {}

    if data.get("reset") is True:
        return jsonify(reset_timeline())

    heartbeat = data.get("heartbeat") or data

    return jsonify(update_timeline(heartbeat))



@app.route("/api/kernel/phase/lock", methods=["GET"], endpoint="api_kernel_phase_lock")
def api_kernel_phase_lock():
    return jsonify(detect_phase_lock(load_timeline()))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
