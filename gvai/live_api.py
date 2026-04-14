from flask import Flask, jsonify, request
from gvai.chat import GvChat

app = Flask(__name__)
chat_engine = GvChat()


@app.get("/")
def home():
    return jsonify({
        "ok": True,
        "message": "GvAI live API",
        "routes": ["/", "/health", "/state", "/reset", "/chat"]
    })


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/reset")
def reset():
    return jsonify(chat_engine.reset())


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    
    # 🔥 FORCE fresh read every time
    user_text = str(data.get("message") or data.get("input") or "").strip()

    if not user_text:
        return jsonify({"ok": False, "error": "Missing message"}), 400

    result = chat_engine.chat(user_text)
    return jsonify(result)


@app.get("/state")
def state():
    if chat_engine.last_result is None:
        return jsonify({
            "ok": True,
            "conversation": {
                "canonical_gv": 1.0,
                "conversation_gv": 1.0,
                "state": "STABLE",
                "turn_index": 0,
            }
        })

    return jsonify({
        "ok": True,
        "conversation": chat_engine.last_result["conversation"],
        "last_decision": chat_engine.last_result["decision"],
        "last_metrics": chat_engine.last_result["metrics"],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
