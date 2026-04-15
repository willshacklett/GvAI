from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from gvai.chat import GvChat

app = Flask(__name__, static_folder="../dashboard")
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

chat_engine = GvChat()


def _state_payload():
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
        "input": result.get("input", user_text),
        "decision": result.get("decision"),
        "metrics": metrics,
        "conversation": conversation,
        "gv_state": result.get("gv_state", {}),
        "timestamp": result.get("timestamp"),
        "message": result.get("reply", ""),
        "godscore": conversation.get("conversation_gv"),
        "state": conversation.get("state"),
        "turn_index": conversation.get("turn_index"),
    }


@app.get("/")
def home():
    try:
        return send_from_directory("../dashboard", "index.html")
    except Exception:
        return jsonify({
            "ok": True,
            "message": "GvAI live API",
            "routes": [
                "/",
                "/health",
                "/state",
                "/reset",
                "/chat",
                "/api/health",
                "/api/state",
                "/api/reset",
                "/api/chat",
            ],
        })


@app.get("/health")
@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/state")
@app.get("/api/state")
def state():
    return jsonify(_state_payload())


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
