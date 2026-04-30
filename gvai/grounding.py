from pathlib import Path
import json, re
from datetime import datetime

KNOWLEDGE_DIR = Path("data/knowledge")
INDEX_PATH = KNOWLEDGE_DIR / "index.json"

def _chunk_text(text, size=900, overlap=150):
    text = re.sub(r"\s+", " ", text or "").strip()
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i:i+size])
        i += max(1, size - overlap)
    return chunks

def rebuild_index():
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    docs = []
    for p in KNOWLEDGE_DIR.glob("*.txt"):
        raw = p.read_text(encoding="utf-8", errors="ignore")
        for n, chunk in enumerate(_chunk_text(raw)):
            docs.append({"source": p.name, "chunk_id": n, "text": chunk})
    INDEX_PATH.write_text(json.dumps({"ok": True, "count": len(docs), "docs": docs}, indent=2), encoding="utf-8")
    return {"ok": True, "count": len(docs)}

def load_index():
    if not INDEX_PATH.exists():
        rebuild_index()
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))

def search_knowledge(query, limit=5):
    q_words = set(re.findall(r"[a-zA-Z0-9_]+", (query or "").lower()))
    scored = []
    for doc in load_index().get("docs", []):
        words = set(re.findall(r"[a-zA-Z0-9_]+", doc["text"].lower()))
        score = len(q_words & words)
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"score": s, "source": d["source"], "chunk_id": d["chunk_id"], "text": d["text"]} for s, d in scored[:limit]]

def grounding_packet(query):
    hits = search_knowledge(query)
    return {
        "grounded": bool(hits),
        "context": "\n\n".join(f"[{h['source']}#{h['chunk_id']}]\n{h['text']}" for h in hits),
        "sources": [{"source": h["source"], "chunk_id": h["chunk_id"], "score": h["score"]} for h in hits],
    }
