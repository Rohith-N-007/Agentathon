"""Offline tests: run with  py test_agent.py   (uses cached demo mode and a throwaway database)."""
import os, tempfile
os.environ["USE_CACHE"] = "1"
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
import demo_cases as D, memory
from agent import run_agent
from llm import ScriptedDriver

def run(student, user, driver=None, expected=None):
    code = {"A": D.STUDENT_A_A, "B": D.STUDENT_B_A, "C": D.STUDENT_C_A}[student]
    events = []
    out = run_agent(driver or ScriptedDriver(user), user, D.PROBLEM, code, "Wrong Answer", lambda q, o: "fewer",
                    on_event=events.append, expected_output=expected)
    return out, events

for s, exp in (("A", None), ("B", None), ("C", D.DISCONNECTED_EXPECTED)):
    out, ev = run(s, f"user_{s}", expected=exp)
    tools = [e["tool"] for e in ev if e["kind"] == "call"]
    st = out["state"]
    print(s, "tools:", tools)
    print("  conclusive:", st["conclusive"], "| error_type:", st["error_type"], "| fingerprint:", memory.get_fingerprint(f"user_{s}"))
    assert st["conclusive"] and memory.get_fingerprint(f"user_{s}"), "should have updated memory"
    assert tools == ["classify_failure","read_memory","mutate_code","generate_test_input","request_prediction","run_counterfactual","update_memory","select_problems"]
syl = [e for e in ev if e["kind"]=="result" and e["tool"]=="select_problems"][0]["payload"]["syllabus"]
print("syllabus:", [(x["problem_id"], x["targets"]) for x in syl])

# HARD RULE: update_memory before a conclusive experiment must be refused and must not change memory.
class Bad:
    def start(self, s, u): return {"type": "call", "name": "update_memory", "args": {"user_id": "cheater"}}
    def step(self, n, r): self.r = r; return {"type": "text", "text": "done"}
d = Bad(); out, ev = run("A", "cheater", driver=d)
print("premature update_memory ->", d.r)
assert "refused" in d.r["error"] and memory.get_fingerprint("cheater") == {}

# Unknown tool and tool exceptions return errors to the model instead of crashing the loop.
class Odd:
    n = 0
    def start(self, s, u): return {"type": "call", "name": "nope", "args": {}}
    def step(self, n, r):
        self.n += 1; self.r = r
        return {"type": "call", "name": "mutate_code", "args": {"bogus": 1}} if self.n == 1 else {"type": "text", "text": "ok"}
d = Odd(); out, ev = run("A", "odd", driver=d)
print("loop survived bad calls ->", out["final"])

# Step cap.
class Loop:
    def start(self, s, u): return {"type": "call", "name": "read_memory", "args": {}}
    def step(self, n, r): return {"type": "call", "name": "read_memory", "args": {}}
out, ev = run("A", "loop", driver=Loop()); print("step cap ->", out["final"])
print("trace rows:", memory.conn().execute("select count(*) from trace").fetchone()[0])
print("ALL OK")
