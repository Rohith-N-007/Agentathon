"""The agent loop. Plain Python while-loop with a step cap, hard rules, and a full trace.

CLI demo (offline, cached):   py agent.py A     (A, B or C)
Live Gemini:                  set GEMINI_API_KEY, then py agent.py A --live
"""
import sys

import demo_cases as D
import memory
from llm import SYSTEM_PROMPT, DEMO_META, GeminiDriver, ScriptedDriver, _student_for
from tools import TOOLS, TOOL_DECLS

MAX_STEPS = 12


def run_agent(driver, user_id, problem, code, verdict, get_prediction, on_event=None, problem_id="p1",
              failing_case="", expected_output=None):
    memory.init_db()
    sub_id = memory.add_submission(user_id, problem_id, "python", code, verdict, failing_case)
    state = dict(user_id=user_id, submission_id=sub_id, problem=problem, code=code, verdict=verdict,
                 failing_case=failing_case, problem_id=problem_id, get_prediction=get_prediction,
                 expected_output=expected_output, retries=0, conclusive=False, result=None)

    def emit(step, kind, tool, payload):
        memory.log_trace(sub_id, step, kind, tool, payload)
        if on_event:
            on_event({"step": step, "kind": kind, "tool": tool, "payload": payload})

    user_msg = f"Problem:\n{problem}\n\nVerdict: {verdict}\nFailing case: {failing_case or 'n/a'}\n\nStudent code:\n{code}"
    msg = driver.start(SYSTEM_PROMPT, user_msg)
    for step in range(MAX_STEPS):
        if msg["type"] == "text":
            emit(step, "final", None, msg["text"])
            return {"final": msg["text"], "state": state}
        name, args = msg["name"], msg["args"]
        emit(step, "call", name, args)
        try:
            fn = TOOLS[name]
            result = fn(state, **args)
        except KeyError:
            result = {"error": f"unknown tool {name}"}
        except Exception as e:                      # tool failures go back to the model, never crash the loop
            result = {"error": f"{type(e).__name__}: {e}"}
        emit(step, "result", name, result)
        msg = driver.step(name, result)
    emit(MAX_STEPS, "final", None, "Stopped: step limit reached.")
    return {"final": "Stopped: step limit reached.", "state": state}


def make_driver(live: bool, user_id: str):
    if live:
        return GeminiDriver(TOOL_DECLS)
    return ScriptedDriver(user_id)


if __name__ == "__main__":
    student = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
    live = "--live" in sys.argv
    code = {"A": D.STUDENT_A_A, "B": D.STUDENT_B_A, "C": D.STUDENT_C_A}[student]
    expected = D.DISCONNECTED_EXPECTED if student == "C" else None
    drv = make_driver(live, "demo")
    out = run_agent(drv, "demo", D.PROBLEM, code, "Wrong Answer" if student == "C" else "Time Limit Exceeded",
                    get_prediction=lambda q, o: (input(f"{q} {o}: ").strip() or "fewer"), on_event=lambda e: print(e["step"], e["kind"], e["tool"], str(e["payload"])[:110]),
                    expected_output=expected)
    print("\nFINAL:", out["final"])
    print("Fingerprint:", memory.get_fingerprint("demo"))
