import os
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from gvai.conscience_routes import register_conscience_routes
from gvai.conscience import evaluate_action

app = Flask(__name__)

register_conscience_routes(app)
CORS(app, resources={r"/api/*": {"origins": "*"}})

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"ok": False, "error": "Missing message"}), 400

    live = search_web(message) if needs_live_search(message) else []

    system = """You are GvAI, a survivability-first AI built around the God Variable.
Answer clearly, honestly, and practically.
If live context is provided, use it. If context is incomplete, say so.
Track stability, drift, recoverability, and irreversibility risk.
Do not pretend stale knowledge is current."""

    user_content = message
    if live:
        user_content += "\n\nLIVE_WEB_CONTEXT:\n" + "\n".join(f"- {x}" for x in live)

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            temperature=0.35,
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    payload = {
        "ok": True,
        "reply": reply,
        "response": reply,
        "live_sources": live,
        "live_search": live,
        "decision": "ANSWER_WITH_LIVE_CONTEXT" if live else "ANSWER",
        "timestamp": time.time()
    }
    return jsonify(attach_gv_conscience(payload, message, reply))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)


def attach_gv_conscience(payload, user_message="", reply_text=""):
    """
    Attach GV conscience judgment to any chat response.
    This makes GV a runtime behavior layer, not just a standalone endpoint.
    """
    if not isinstance(payload, dict):
        payload = {"reply": str(payload)}

    action = f"User asked: {user_message}\nAI replied: {reply_text or payload.get('reply', '')}"
    payload["gv"] = evaluate_action(action)
    return payload

