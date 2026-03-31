from fastapi import FastAPI
from pydantic import BaseModel

from gvai.real_gv import evaluate_real_gv

app = FastAPI()

@app.get("/")
def root():
    return {
        "name": "GvAI Gateway",
        "status": "live",
        "endpoints": ["/health", "/gv/state", "/chat"]
    }

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/gv/state")
def gv_state():
    return evaluate_real_gv()

class ChatRequest(BaseModel):
    message: str
    provider: str = "openai"

@app.post("/chat")
def chat(req: ChatRequest):
    gv = evaluate_real_gv()

    return {
        "gv_decision": gv.get("decision"),
        "gv_response": gv.get("response"),
        "input": req.message,
        "status": "governed"
    }
