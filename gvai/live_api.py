from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pathlib import Path

from gvai.grounding import grounding_packet, search_knowledge, rebuild_index
from gvai.web_search import search_web
from gvai.conscience import evaluate_action, gv_conscience_statement
from gvai.conscience_routes import register_conscience_routes
from gvai.kernel.runtime import score_runtime
from gvai.kernel.trajectory import load_state, reset_state, update_state

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
