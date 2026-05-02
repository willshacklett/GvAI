import os
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from gvai.conscience_routes import register_conscience_routes
from gvai.conscience import evaluate_action
from gvai.model_router import call_model, active_provider, available_providers

app = Flask(__name__)

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

    system = """You are GvAI, a survivability-first AI built around the God Variable.
Answer clearly, honestly, and practically.
If live context is provided, use it. If context is incomplete, say so.
Track stability, drift, recoverability, and irreversibility risk.
Do not pretend stale knowledge is current.

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
        qualified_reply = str(original_reply) + "\n\nGV qualification: this answer is usable only with constraints. Verify assumptions, keep rollback available, monitor drift, and avoid irreversible action."
        payload["reply"] = qualified_reply
        payload["response"] = qualified_reply
        payload["gv_enforced"] = True
    else:
        payload["gv_enforced"] = False

    payload["gv"] = gv_judgment
    return payload

