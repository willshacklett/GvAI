from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# 🔥 CORS FIX
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later we can lock this down
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Input(BaseModel):
    text: str

@app.get("/")
def root():
    return {"status": "gvai live"}

@app.post("/score")
def score(input: Input):
    text = input.text

    length = len(text)
    words = text.split()

    gv = min(1.0, max(0.0, len(words) / 20))

    decision = "allow"
    if gv > 0.7:
        decision = "block"
    elif gv > 0.4:
        decision = "warn"

    return {
        "gv": gv,
        "decision": decision,
        "signal": {
            "sentence_count": text.count("."),
            "avg_len": length / max(1, len(words)),
        }
    }
