"""FastAPI app: start a run, stream trace events (SSE), answer the prediction gate, read results.
Run:  uvicorn main:app --reload     (use plain `uvicorn main:app` for the demo if SSE hangs on Windows)
"""
import json
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import demo_cases as D
import memory
from agent import run_agent, make_driver

app = FastAPI(title="Why-Did-I-Fail Coach")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])
memory.init_db()

RUNS = {}   # run_id -> dict(events, prediction_event, prediction, done, result)
DEMO = {"A": D.STUDENT_A_A, "B": D.STUDENT_B_A, "C": D.STUDENT_C_A}


class StartRun(BaseModel):
    user_id: str = "demo"
    student: str | None = None          # "A" | "B" | "C" loads a cached demo submission
    problem: str | None = None
    code: str | None = None
    verdict: str = "Wrong Answer"
    failing_case: str = ""
    live: bool = False                  # True = Gemini drives the loop; False = scripted fallback


class Prediction(BaseModel):
    guess: str                          # "more" | "fewer" | "same"


@app.post("/runs")
def start_run(body: StartRun):
    code = DEMO.get((body.student or "").upper()) or body.code
    if not code:
        raise HTTPException(400, "send `student` (A/B/C) or `code`")
    run_id = uuid.uuid4().hex[:8]
    run = dict(events=[], prediction_event=threading.Event(), prediction=None, done=False, result=None, error=None)
    RUNS[run_id] = run
    expected = D.DISCONNECTED_EXPECTED if (body.student or "").upper() == "C" else None

    def on_event(e):
        run["events"].append(e)

    def get_prediction(question, options):
        run["events"].append({"step": -1, "kind": "prediction_request", "tool": "request_prediction",
                              "payload": {"question": question, "options": options}})
        run["prediction_event"].wait(timeout=120)
        return run["prediction"] or "no answer"

    def work():
        try:
            driver = make_driver(body.live, body.user_id)
            out = run_agent(driver, body.user_id, body.problem or D.PROBLEM, code, body.verdict, get_prediction,
                            on_event=on_event, failing_case=body.failing_case, expected_output=expected)
            st = out["state"]
            run["result"] = {"final": out["final"], "error_type": st.get("error_type"), "experiment": st.get("result"),
                             "conclusive": st.get("conclusive"), "prediction": st.get("prediction"),
                             "code_a": st.get("code_a"), "code_b": st.get("code_b")}
        except Exception as e:                                  # surface errors to the UI instead of hanging
            run["error"] = f"{type(e).__name__}: {e}"
        finally:
            run["done"] = True

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": run_id}


def _get(run_id):
    if run_id not in RUNS:
        raise HTTPException(404, "unknown run")
    return RUNS[run_id]


@app.get("/runs/{run_id}/events")
def events(run_id: str, since: int = 0):
    run = _get(run_id)
    return {"events": run["events"][since:], "next": len(run["events"]), "done": run["done"], "error": run["error"]}


@app.get("/runs/{run_id}/stream")
def stream(run_id: str):
    run = _get(run_id)

    def gen():
        i = 0
        while True:
            while i < len(run["events"]):
                yield f"data: {json.dumps(run['events'][i], default=str)}\n\n"
                i += 1
            if run["done"]:
                yield f"event: done\ndata: {json.dumps({'error': run['error']})}\n\n"
                return
            time.sleep(0.1)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/runs/{run_id}/prediction")
def prediction(run_id: str, body: Prediction):
    run = _get(run_id)
    run["prediction"] = body.guess
    run["prediction_event"].set()
    return {"ok": True}


@app.get("/runs/{run_id}/result")
def result(run_id: str):
    run = _get(run_id)
    if not run["done"]:
        raise HTTPException(202, "still running")
    return {"result": run["result"], "error": run["error"]}


@app.get("/fingerprint/{user_id}")
def fingerprint(user_id: str):
    return memory.get_fingerprint(user_id)


@app.get("/reviews/{user_id}")
def reviews(user_id: str):
    return memory.due_reviews(user_id)
