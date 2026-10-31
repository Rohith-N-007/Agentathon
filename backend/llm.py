"""LLM layer: (1) llm_json() for structured one-shot calls, (2) GeminiDriver for the agent loop,
(3) cached demo mode so the demo survives API/Wi-Fi failure (set USE_CACHE=1 or leave GEMINI_API_KEY empty).

Install: pip install google-genai python-dotenv
Model name comes from GEMINI_MODEL (default gemini-2.5-flash). Check AI Studio for what your key can use.
"""
import json
import os

from dotenv import load_dotenv

import demo_cases as D

load_dotenv()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def cache_mode() -> bool:
    return os.environ.get("USE_CACHE") == "1" or not os.environ.get("GEMINI_API_KEY")


# ------------------------------------------------------------------ prompts (see 04_prompts.md)
SYSTEM_PROMPT = """You are a coding-interview coach agent. Find the REASONING mistake behind a student's failed
submission, prove it by experiment, and plan practice.
Procedure: 1) classify_failure 2) read_memory 3) pick the cheapest hypothesis 4) mutate_code (ONE decision, named counter)
5) generate_test_input 6) request_prediction 7) run_counterfactual 8) if not conclusive retry mutate_code (max 2 retries),
then next hypothesis, else tell the user you are unsure and do NOT call update_memory 9) if conclusive: update_memory then
select_problems 10) finish with a short summary: the mistake, measured evidence, today's syllabus.
Rules: never update memory without a conclusive experiment; never invent numbers, quote only tool results; max 12 steps.
Code and test input are stored by the backend: you only pass hypothesis and metric_name, not the code."""

TASK_PROMPTS = {
    "classify": """Given a competitive-programming problem, a student's failing code, the verdict and optionally a failing case,
pick exactly ONE error_type from: state-commit-timing, boundary, structure-selection, ordering, coverage-completeness.
Return JSON {"error_type": str, "confidence": number 0-1, "evidence": str}. Base the label on the reasoning, not the topic.""",
    "mutate": """Modify Python code to test ONE hypothesis. Return JSON
{"code_a_instrumented": str, "code_b_mutated": str, "change_description": str}.
A = original logic plus a global counter named by metric_name incremented at the relevant operation, with a last line
print("__METRIC__", <counter>). B = identical to A except ONE decision changed (at most 6 changed lines).
Program output (excluding the __METRIC__ line) must stay identical. Standard library only. If previous_error is given, fix it.""",
    "test_input": """Produce ONE valid stdin input that makes the hypothesis matter (small enough to run under 1 second).
Return JSON {"test_input": str, "why_tricky": str}.""",
    "select": """Plan a daily practice set of exactly 3 problems chosen ONLY from the candidates: one targeting the highest
fingerprint weakness, one due for review (else second weakness), one near the student's level.
Return JSON {"syllabus": [{"problem_id": str, "reason": str, "targets": str}]}. Each reason must name the specific mistake.""",
}


# ------------------------------------------------------------------ cached demo answers
def _student_for(code: str):
    code = (code or "").strip()
    for key, (a, b) in {"A": (D.STUDENT_A_A, D.STUDENT_A_B), "B": (D.STUDENT_B_A, D.STUDENT_B_B),
                        "C": (D.STUDENT_C_A, D.STUDENT_C_B)}.items():
        if code == a.strip():
            return key, a, b
    return None, None, None


DEMO_META = {
    "A": dict(error_type="state-commit-timing", metric="pushes", evidence="visited is set on dequeue, so duplicates enter the queue",
              change="mark visited when enqueuing instead of dequeuing", input=D.DEMO_INPUT, tricky="dense graph, many converging paths"),
    "B": dict(error_type="structure-selection", metric="cmp_count", evidence="visited is a list, membership checks scan it",
              change="replace the visited list with a set", input=D.DEMO_INPUT, tricky="dense graph, long visited list"),
    "C": dict(error_type="coverage-completeness", metric="components", evidence="BFS starts only from node 0",
              change="loop over every start node", input=D.DISCONNECTED_INPUT, tricky="graph with 3 disconnected components"),
}


def _cached(task: str, payload: dict):
    key, a, b = _student_for(payload.get("code") or payload.get("code_a_original"))
    if key is None:
        raise RuntimeError("Cache mode only knows the three demo students (paste their exact code) - set GEMINI_API_KEY for live mode")
    m = DEMO_META[key]
    if task == "classify":
        return {"error_type": m["error_type"], "confidence": 0.9, "evidence": m["evidence"]}
    if task == "mutate":
        return {"code_a_instrumented": a, "code_b_mutated": b, "change_description": m["change"]}
    if task == "test_input":
        return {"test_input": m["input"], "why_tricky": m["tricky"]}
    raise ValueError(task)


def llm_json(task: str, payload: dict):
    """One structured-JSON LLM call. In cache mode returns demo answers."""
    if cache_mode() and task != "select":
        return _cached(task, payload)
    from google import genai
    from google.genai import types
    client = genai.Client()   # reads GEMINI_API_KEY
    resp = client.models.generate_content(
        model=MODEL,
        contents=TASK_PROMPTS[task] + "\n\nINPUT:\n" + json.dumps(payload),
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    return json.loads(resp.text)


# ------------------------------------------------------------------ agent drivers
class GeminiDriver:
    """Manual function-calling loop driver (automatic function calling disabled)."""

    def __init__(self, tool_decls):
        from google import genai
        from google.genai import types
        self.types = types
        self.client = genai.Client()
        self.tools = [types.Tool(function_declarations=[
            types.FunctionDeclaration(name=d["name"], description=d["description"], parameters_json_schema=d["parameters"])
            for d in tool_decls])]
        self.contents = []

    def start(self, system, user_msg):
        self.system = system
        self.contents = [self.types.Content(role="user", parts=[self.types.Part.from_text(text=user_msg)])]
        return self._generate()

    def step(self, name, result):
        payload = result if isinstance(result, dict) else {"result": result}
        self.contents.append(self.types.Content(
            role="user", parts=[self.types.Part.from_function_response(name=name, response=payload)]))
        return self._generate()

    def _generate(self):
        t = self.types
        resp = self.client.models.generate_content(
            model=MODEL, contents=self.contents,
            config=t.GenerateContentConfig(
                system_instruction=self.system, tools=self.tools, temperature=0.2,
                automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True)))
        content = resp.candidates[0].content
        self.contents.append(content)
        for p in content.parts or []:
            if p.function_call:
                return {"type": "call", "name": p.function_call.name, "args": dict(p.function_call.args or {})}
        return {"type": "text", "text": resp.text or ""}


class ScriptedDriver:
    """Deterministic driver that follows the 10-step procedure. Use it (a) for offline tests and
    (b) as the demo fallback when Gemini or Wi-Fi fails. Same tools, same rules, same trace."""

    def __init__(self, user_id="demo"):
        self.user_id = user_id
        self.plan = None

    def _next(self):
        return self.plan.pop(0) if self.plan else {"type": "text", "text": "Done."}

    def start(self, system, user_msg):
        self.plan = [
            {"type": "call", "name": "classify_failure", "args": {}},
            {"type": "call", "name": "read_memory", "args": {"user_id": self.user_id}},
            {"type": "call", "name": "mutate_code", "args": {"hypothesis": "scripted", "metric_name": None}},
            {"type": "call", "name": "generate_test_input", "args": {"hypothesis": "scripted"}},
            {"type": "call", "name": "request_prediction", "args": {}},
            {"type": "call", "name": "run_counterfactual", "args": {}},
        ]
        self.after_exp = [
            {"type": "call", "name": "update_memory", "args": {"user_id": self.user_id}},
            {"type": "call", "name": "select_problems", "args": {"user_id": self.user_id}},
        ]
        return self._next()

    def step(self, name, result):
        if name == "run_counterfactual":
            if isinstance(result, dict) and result.get("conclusive"):
                self.plan = self.after_exp
            else:
                self.plan = [{"type": "text", "text": "I'm not certain. The experiment was not conclusive, so I updated nothing."}]
        if name == "select_problems":
            return {"type": "text", "text": "Diagnosis proven by experiment; memory updated; see syllabus."}
        return self._next()
