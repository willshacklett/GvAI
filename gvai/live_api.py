from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from gvai.chat import GvChat
from gvai.web_search import search_web
from gvai.ai_bridge import chat_provider, available_providers

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DASHBOARD_DIR = ROOT / "dashboard"

app = Flask(__name__, static_folder=str(DASHBOARD_DIR))
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

chat_engine = GvChat()

def _conversation_payload():
    state = chat_engine.get_state()
    conversation = state.get("conversation", {})
    metrics = state.get("last_metrics", {}) or {}
    decision = state.get("last_decision")
    gv_state = state.get("gv_state", {})
    return {
        "ok": True,
        "conversation": conversation,
        "last_decision": decision,
        "last_metrics": metrics,
        "gv_state": gv_state,
        "signal": {
            "godscore": conversation.get("conversation_gv"),
            "state": conversation.get("state"),
            "turn_index": conversation.get("turn_index"),
            "decision": decision,
        },
    }

def _chat_payload(user_text: str, gv_state=None):
    result = chat_engine.chat(user_text, gv_state=gv_state)
    conversation = result.get("conversation", {})
    metrics = result.get("metrics", {}) or {}
    return {
        "ok": True,
        "reply": result.get("reply", ""),
        "message": result.get("reply", ""),
        "response": result.get("reply", ""),
        "input": result.get("input", user_text),
        "decision": result.get("decision"),
        "metrics": metrics,
        "conversation": conversation,
        "gv_state": result.get("gv_state", {}),
        "timestamp": result.get("timestamp"),
        "godscore": conversation.get("conversation_gv"),
        "state": conversation.get("state"),
        "turn_index": conversation.get("turn_index"),
    }

@app.get("/")
def root():
    target = WEB_DIR / "index.html"
    if target.exists():
        return send_from_directory(str(WEB_DIR), "index.html")
    return jsonify({
        "ok": True,
        "message": "GvAI live API",
        "routes": ["/", "/health", "/state", "/reset", "/chat", "/api/health", "/api/state", "/api/reset", "/api/chat"],
    })

@app.get("/dashboard")
def dashboard_index():
    target = DASHBOARD_DIR / "index.html"
    if target.exists():
        return send_from_directory(str(DASHBOARD_DIR), "index.html")
    return jsonify({"ok": False, "error": "dashboard/index.html not found"}), 404

@app.get("/dashboard/<path:filename>")
def dashboard_files(filename: str):
    return send_from_directory(str(DASHBOARD_DIR), filename)


@app.get("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory("assets", filename)

@app.get("/style.css")
def root_style():
    return send_from_directory(str(DASHBOARD_DIR), "style.css")

@app.get("/dashboard.js")
def root_js():
    return send_from_directory(str(DASHBOARD_DIR), "dashboard.js")

@app.get("/conversation_gv_demo.json")
def root_demo_json():
    return send_from_directory(str(DASHBOARD_DIR), "conversation_gv_demo.json")

@app.get("/gvai_state.json")
def root_state_json():
    return send_from_directory(str(DASHBOARD_DIR), "gvai_state.json")

@app.get("/health")
@app.get("/api/health")
def health():
    return jsonify({"ok": True})

@app.get("/state")
@app.get("/api/state")
def state():
    return jsonify(_conversation_payload())

@app.post("/reset")
@app.post("/api/reset")
def reset():
    return jsonify(chat_engine.reset())

@app.route("/chat", methods=["GET", "POST"])
@app.route("/api/chat", methods=["GET", "POST"])
def chat():
    gv_state = None
    if request.method == "GET":
        user_text = str(request.args.get("message") or request.args.get("input") or "").strip()
    else:
        data = request.get_json(silent=True) or {}
        user_text = str(data.get("message") or data.get("input") or "").strip()
        gv_state = data.get("gv_state")
    if not user_text:
        return jsonify({"ok": False, "error": "Missing message"}), 400
    return jsonify(_chat_payload(user_text, gv_state=gv_state))



@app.post("/api/search")
def api_search():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    max_results = int(payload.get("max_results") or 5)
    result = search_web(query, max_results=max_results)
    return jsonify(result)

@app.get("/api/providers")
def api_providers():
    return jsonify({
        "providers": available_providers()
    })

@app.post("/api/ai/chat")
def api_ai_chat():
    payload = request.get_json(silent=True) or {}
    provider = (payload.get("provider") or "openai").strip()
    message = payload.get("message")
    messages = payload.get("messages") or []
    system_prompt = payload.get("system_prompt")
    model = payload.get("model")

    result = chat_provider(
        provider,
        message=message,
        messages=messages,
        system_prompt=system_prompt,
        model=model,
    )
    return jsonify(result)

@app.post("/api/ai/compare")
def api_ai_compare():
    payload = request.get_json(silent=True) or {}
    providers = payload.get("providers") or available_providers()
    message = payload.get("message")
    messages = payload.get("messages") or []
    system_prompt = payload.get("system_prompt")
    model_map = payload.get("models") or {}

    out = {
        "providers": [],
        "results": [],
        "errors": [],
    }

    for provider in providers:
        try:
            result = chat_provider(
                provider,
                message=message,
                messages=messages,
                system_prompt=system_prompt,
                model=model_map.get(provider),
            )
            out["providers"].append(provider)
            out["results"].append(result)
        except Exception as e:
            out["errors"].append({
                "provider": provider,
                "error": str(e),
            })

    return jsonify(out)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
