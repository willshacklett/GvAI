from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

def extract_signal(text: str):
    normalized = text.replace("!", ".").replace("?", ".")
    sentences = [s.strip() for s in normalized.split(".") if s.strip()]
    sentence_count = len(sentences) if sentences else 1

    words = [w.strip(".,;:!?\"'()[]{}").lower() for w in text.split()]
    words = [w for w in words if w]
    word_count = len(words) if words else 1

    avg_sentence_words = word_count / sentence_count
    long_word_ratio = sum(1 for w in words if len(w) >= 7) / word_count

    punct_count = sum(text.count(ch) for ch in [",", ";", ":", "-", "!", "?"])
    punct_per_word = punct_count / word_count

    unique_ratio = len(set(words)) / word_count
    repetition = 1.0 - unique_ratio

    return {
        "sentence_count": clamp((sentence_count - 1) / 3.0),
        "avg_len": clamp((avg_sentence_words - 6.0) / 16.0),
        "punctuation": clamp(punct_per_word * 14.0),
        "long_words": clamp(long_word_ratio * 5.0),
        "repetition": clamp(repetition * 3.0),
    }

def compute_gv(signal):
    return round(
        0.34 * signal["avg_len"] +
        0.20 * signal["long_words"] +
        0.14 * signal["punctuation"] +
        0.12 * signal["repetition"] +
        0.12 * signal["sentence_count"],
        3
    )

class Request(BaseModel):
    text: str

@app.get("/")
def root():
    return {"status": "gvai live"}

@app.post("/score")
def score(req: Request):
    signal = extract_signal(req.text)
    gv = compute_gv(signal)

    if gv < 0.35:
        decision = "allow"
    elif gv < 0.70:
        decision = "warn"
    else:
        decision = "block"

    return {
        "gv": gv,
        "decision": decision,
        "signal": signal
    }
