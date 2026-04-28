import os
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
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

    gv = 0.86 if live else 0.91
    state = "STABLE" if gv >= 0.85 else "DEGRADED"

    return jsonify({
        "ok": True,
        "reply": reply,
        "response": reply,
        "gv": gv,
        "state": state,
        "decision": "ANSWER_WITH_LIVE_CONTEXT" if live else "ANSWER",
        "drift_risk": "LOW" if gv >= 0.85 else "MEDIUM",
        "irreversibility_risk": "LOW",
        "live_search": live,
        "timestamp": time.time()
    })
