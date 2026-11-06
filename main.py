from fastapi import FastAPI
from pydantic import BaseModel

from build_index import search, tickets
from incident_state import new_incident, update_incident

app = FastAPI()

THRESHOLD = 0.263

# session_id -> {"incident": {...}, "last_results": None}
sessions: dict = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.post("/chat")
def chat(req: ChatRequest):
    if req.session_id not in sessions:
        sessions[req.session_id] = {"incident": new_incident(), "last_results": None}

    session = sessions[req.session_id]
    incident, should_refresh = update_incident(req.message, incident=session["incident"])

    if should_refresh and incident["symptoms"]:
        query = " ".join(incident["symptoms"])
        raw = search(query, component=incident["component"])

        if raw and raw[0][0] >= THRESHOLD:
            session["last_results"] = [
                {
                    "case_number": tickets[idx]["case_number"],
                    "score":       round(score, 4),
                    "short_description": tickets[idx]["short_description"],
                    "component":   tickets[idx]["component"],
                }
                for score, idx in raw
            ]
        else:
            session["last_results"] = "no similar ticket found"

    return {
        "session_id":    req.session_id,
        "refreshed":     should_refresh,
        "incident":      incident,
        "results":       session["last_results"],
    }
