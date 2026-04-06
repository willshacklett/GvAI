from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

class Req(BaseModel):
    text: str | None = None

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/score")
def score(req: Req):
    return {
        "ok": True,
        "text": req.text,
        "score": 99.08,
        "passed": True,
        "fired": False,
        "lead_time": 59.45,
        "mean_step": 0.467167,
        "drift_step": None,
        "breach_step": None,
        "collapse_step": None,
        "tone": "clean",
        "reasons": ["Signal remains inside the stable boundary."]
    }

app.mount("/", StaticFiles(directory=".", html=True), name="site")
