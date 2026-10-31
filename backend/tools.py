"""Tool implementations + Gemini tool declarations. The backend keeps code/inputs in `state`,
so the model never has to paste large code blocks into function arguments."""
import memory
from llm import llm_json, DEMO_META, _student_for
from sandbox import run_counterfactual as sandbox_run

ERROR_TYPES = ["state-commit-timing", "boundary", "structure-selection", "ordering", "coverage-completeness"]

TOOL_DECLS = [
    {"name": "classify_failure", "description": "Label the most likely reasoning error behind the failed submission (backend supplies the code).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "read_memory", "description": "Read the student's fingerprint scores and due reviews.",
     "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]}},
    {"name": "mutate_code", "description": "Change ONE decision in the student's code to test a hypothesis and insert a named counter. Backend stores versions A and B.",
     "parameters": {"type": "object", "properties": {
         "hypothesis": {"type": "string"}, "metric_name": {"type": "string", "description": "counter to insert, e.g. pushes"},
         "previous_error": {"type": "string", "description": "validation error from the last attempt, if retrying"}},
         "required": ["hypothesis", "metric_name"]}},
    {"name": "generate_test_input", "description": "Produce a tricky valid input that should expose the difference between A and B.",
     "parameters": {"type": "object", "properties": {"hypothesis": {"type": "string"}}, "required": ["hypothesis"]}},
    {"name": "request_prediction", "description": "Ask the student to predict the effect before running. Blocks until they answer.",
     "parameters": {"type": "object", "properties": {"question": {"type": "string"},
                                                       "options": {"type": "array", "items": {"type": "string"}}}}},
    {"name": "run_counterfactual", "description": "Run A and B on the test input in the sandbox; returns measured counts and whether the result is conclusive.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "update_memory", "description": "Update the fingerprint and schedule a review. Allowed ONLY after a conclusive experiment.",
     "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]}},
    {"name": "select_problems", "description": "Pick 3 problems for today with a reason each.",
     "parameters": {"type": "object", "properties": {"user_id": {"type": "string"}}, "required": ["user_id"]}},
]


def classify_failure(state, **_):
    r = llm_json("classify", {"problem_statement": state["problem"], "code": state["code"],
                              "verdict": state["verdict"], "failing_case": state.get("failing_case", "")})
    if r.get("error_type") not in ERROR_TYPES:
        return {"error": f"error_type must be one of {ERROR_TYPES}"}
    state["error_type"] = r["error_type"]
    return r


def read_memory(state, user_id=None, **_):
    uid = user_id or state["user_id"]
    return {"fingerprint": memory.get_fingerprint(uid), "due_reviews": memory.due_reviews(uid)}


def mutate_code(state, hypothesis="", metric_name=None, previous_error=None, **_):
    if state["retries"] > 2:
        return {"error": "max retries reached; try the next hypothesis or abstain"}
    key, _, _ = _student_for(state["code"])
    metric = metric_name or state.get("metric") or (DEMO_META[key]["metric"] if key else "pushes")
    r = llm_json("mutate", {"code": state["code"], "code_a_original": state["code"], "hypothesis": hypothesis,
                            "metric_name": metric, "previous_error": previous_error})
    state.update(code_a=r["code_a_instrumented"], code_b=r["code_b_mutated"], metric=metric, hypothesis=hypothesis,
                 conclusive=False, result=None)
    state["retries"] += 1
    return {"change_description": r.get("change_description", ""), "metric": metric, "versions_stored": True}


def generate_test_input(state, hypothesis="", **_):
    r = llm_json("test_input", {"code": state["code"], "problem_statement": state["problem"], "hypothesis": hypothesis,
                                "input_format": state.get("input_format", "see problem")})
    state["test_input"] = r["test_input"]
    return {"why_tricky": r.get("why_tricky", ""), "input_chars": len(r["test_input"])}


def request_prediction(state, question=None, options=None, **_):
    q = question or "Will version B perform more, fewer or the same operations as version A?"
    guess = state["get_prediction"](q, options or ["more", "fewer", "same"])
    state["prediction"] = guess
    return {"guess": guess}


def run_counterfactual(state, **_):
    if not state.get("code_a") or not state.get("test_input"):
        return {"error": "call mutate_code and generate_test_input first"}
    r = sandbox_run(state["code_a"], state["code_b"], state["test_input"], state["metric"], state.get("expected_output"))
    r.pop("stderr_a", None), r.pop("stderr_b", None)
    state["result"], state["conclusive"] = r, bool(r["conclusive"])
    if r["count_a"] is not None and r["count_b"] is not None:
        actual = "fewer" if r["count_b"] < r["count_a"] else "more" if r["count_b"] > r["count_a"] else "same"
        r["prediction_correct"] = (state.get("prediction") == actual)
    state["experiment_id"] = memory.save_experiment(state["submission_id"], state.get("hypothesis", ""), state.get("error_type"),
                                                    state, r, state.get("prediction"))
    return r


def update_memory(state, user_id=None, **_):
    # HARD RULE enforced in code, not only in the prompt:
    if not state.get("conclusive"):
        return {"error": "refused: the experiment is not conclusive, memory must not be updated"}
    fp, due = memory.update_fingerprint(user_id or state["user_id"], state["error_type"], state.get("problem_id"))
    return {"fingerprint": fp, "next_review_date": due}


def select_problems(state, user_id=None, **_):
    uid = user_id or state["user_id"]
    fp, due, problems = memory.get_fingerprint(uid), memory.due_reviews(uid), memory.list_problems()
    ranked = sorted(fp, key=fp.get, reverse=True)
    syllabus, used = [], set()

    def pick(error_type, reason):
        for p in problems:
            if p["id"] not in used and error_type in p["error_types"].split(","):
                used.add(p["id"])
                syllabus.append({"problem_id": p["id"], "title": p["title"], "reason": reason, "targets": error_type})
                return True
        return False

    if ranked:
        pick(ranked[0], f"Targets your top weakness ({ranked[0]}), the mistake just proven by experiment.")
    if due:
        pick(due[0]["error_type"], f"Review due today for {due[0]['error_type']} (spaced repetition).")
    elif len(ranked) > 1:
        pick(ranked[1], f"Second weakness ({ranked[1]}).")
    for p in sorted(problems, key=lambda p: abs(p["difficulty"] - 2)):
        if len(syllabus) >= 3:
            break
        if p["id"] not in used:
            used.add(p["id"])
            syllabus.append({"problem_id": p["id"], "title": p["title"], "reason": "Near your level, mixes skills.", "targets": "mixed"})
    return {"syllabus": syllabus[:3]}
    # TODO (Sakshi): optionally ask the LLM (llm_json("select", ...)) to write richer reasons,
    # but keep the DB choice above as the validated fallback and only allow candidate ids.


TOOLS = {f.__name__: f for f in (classify_failure, read_memory, mutate_code, generate_test_input,
                                 request_prediction, run_counterfactual, update_memory, select_problems)}
