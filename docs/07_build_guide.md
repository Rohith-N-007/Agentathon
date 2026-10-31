# Step-by-Step: Building the Agentic AI (Windows, 24 hours)

You already have a working skeleton. The agent loop, tools, sandbox, memory and API are written and tested offline in cached demo mode (Students A, B, C all end conclusive). Your job in 24 hours is to **make the live Gemini path reliable, build the UI, and rehearse**, not to start from zero.

## What is already tested, and what is not
| Part | Status |
|---|---|
| Sandbox (timeout, memory watchdog, op counts) | Tested on Linux; **re-test on Windows in hour 1** |
| Agent loop, hard rules, retries, trace, SQLite, SM-2, syllabus | Tested offline with a scripted driver (`py test_agent.py`) |
| FastAPI: runs, prediction gate, events, SSE | Tested with FastAPI's test client |
| Gemini live mode (`--live`) | **Not tested**: needs your API key. Code follows the google-genai function-calling docs, but the structured-JSON config (`response_mime_type`) is written from memory, so test it first |
| Next.js UI | Not built |

## Files and who owns them
Put every `.py` file in `backend/`.
| File | What it does | Owner |
|---|---|---|
| `agent.py` | The while-loop: model picks a tool, backend runs it, result goes back. Step cap 12. Logs a trace. | Samhita |
| `llm.py` | Prompts, `llm_json()` for one-shot JSON calls, `GeminiDriver` (live), `ScriptedDriver` (fallback/tests), cached demo answers | Samhita |
| `tools.py` | The 8 tools plus Gemini declarations. Enforces "no memory update unless conclusive" | Samhita + Rohit |
| `sandbox.py` | `run_counterfactual`: runs A and B, counts operations, decides conclusive | Rohit |
| `memory.py`, `sm2.py` | SQLite tables, fingerprint, spaced reviews, problem bank seed | Sakshi |
| `main.py` | REST + SSE API for the UI | Rohit (run routes), Sakshi (data routes) |
| `frontend/` | Dashboard, prediction gate, diff, chart, trace, syllabus | Saanvi |

## How the agent works (one paragraph to understand before editing)
`run_agent()` sends the problem and code to the driver. The driver returns either a **tool call** or **final text**. For a tool call, the backend runs the tool, logs call and result, and returns the result to the driver. The model decides *which* tool and *when*, but the backend decides what is *allowed* (e.g. `update_memory` is refused unless the sandbox said conclusive). The model never pastes code into tool arguments: the backend stores versions A and B and the test input in `state`, so calls stay small and reliable.

---

## Step 0: Setup (all four, hour 0-1)
1. Follow `06_windows_setup.md` (Python, Node, Git, venv).
2. Copy all files into `backend\`. Install dependencies:
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # leave GEMINI_API_KEY empty for now
```
3. Get a Gemini API key from Google AI Studio and put it in `.env` as `GEMINI_API_KEY=...` (never commit `.env`).

## Step 1: Prove the skeleton works on Windows (hour 1, Rohit)
```powershell
py sandbox.py            # count_a 781, count_b 40, conclusive true
py test_agent.py         # prints ALL OK
py agent.py A            # runs Student A in cached mode; type "fewer" at the prediction gate
py agent.py B
py agent.py C
```
If any fail on Windows, fix first. Everything else depends on this.

## Step 2: Start the API and check it (hour 1-2, Rohit)
```powershell
uvicorn main:app --reload
```
Open `http://127.0.0.1:8000/docs`. Try `POST /runs` with `{"student": "A"}`, then `GET /runs/<id>/events`, then `POST /runs/<id>/prediction` with `{"guess": "fewer"}`, then `GET /runs/<id>/result`. This is exactly what the UI will do.

## Step 3: Connect live Gemini (hours 2-5, Samhita) *the riskiest step*
Do it in this order, testing each piece alone:
1. **Check the key and model name**:
```powershell
py -c "from google import genai; c=genai.Client(); print(c.models.generate_content(model='gemini-2.5-flash', contents='say ok').text)"
```
If the model is not found, pick one your key supports in AI Studio and set `GEMINI_MODEL` in `.env`.
2. **Structured JSON** (`llm_json`): temporarily set `USE_CACHE=` empty and call:
```powershell
py -c "from llm import llm_json; import demo_cases as D; print(llm_json('classify', {'problem_statement': D.PROBLEM, 'code': D.STUDENT_A_A, 'verdict': 'TLE', 'failing_case': ''}))"
```
Expect `error_type: state-commit-timing`. If you get a JSON error, add a `response_schema` to the config in `llm_json` or strip code fences before `json.loads`.
3. **Mutation**: call `llm_json('mutate', ...)` with Student A's code, metric `pushes`, then feed the result to `sandbox.run_counterfactual`. The most likely failure is a mutation that changes output or does not compile. This is why we have retries.
4. **Test input**: call `llm_json('test_input', ...)`. Always validate that both versions run on it (the sandbox does).
5. **Full live loop**: `py agent.py A --live`. Read the printed trace. Fix prompts (in `llm.py`) until A, B and C each reach a conclusive result in 3 runs out of 3.

The live path needs `GEMINI_API_KEY` set. Without it, the code silently uses cached demo mode, so always check which mode you are in (`llm.cache_mode()`).

## Step 4: Make failure handling real (hours 5-8, Samhita + Rohit)
Already coded: unknown tools and tool exceptions return an error to the model; `update_memory` refuses unless conclusive; max 2 retries (`state["retries"]`); step cap 12. Still to do:
1. When `run_counterfactual` says not conclusive, return a **reason** (outputs differ, no measurable difference, timeout) so the model can retry sensibly. Add `reason` in `tools.run_counterfactual`.
2. After 2 failed retries, make the agent switch hypothesis, and after the last hypothesis end with the "I'm not certain" message. Test by feeding a submission where the mutation cannot show a difference.
3. Add a test in `test_agent.py` for each reason.

## Step 5: Build the UI (hours 2-12, Saanvi, against the running API)
Screens, in this order:
1. **Submit and trace**: pick Student A/B/C (calls `POST /runs`), then live trace list from SSE.
2. **Prediction gate**: when an event has `kind == "prediction_request"`, show More / Fewer / Same buttons and `POST /runs/{id}/prediction`.
3. **Result view**: when done, `GET /runs/{id}/result`. Bar chart of `experiment.count_a` vs `count_b` and a Monaco diff of `code_a` vs `code_b`. Show "your prediction was correct/incorrect" from `experiment.prediction_correct`.
4. **Fingerprint dashboard**: `GET /fingerprint/{user_id}`, bars per error type.
5. **Syllabus**: the `select_problems` result is in the trace; also show it from the final events.

SSE in the browser (use `127.0.0.1`, not `localhost`, to avoid IPv6 issues on Windows):
```js
const es = new EventSource(`http://127.0.0.1:8000/runs/${runId}/stream`);
es.onmessage = (m) => {
  const e = JSON.parse(m.data);          // {step, kind: call|result|final|prediction_request, tool, payload}
  setTrace((t) => [...t, e]);
  if (e.kind === "prediction_request") setGate(e.payload);   // {question, options}
};
es.addEventListener("done", () => es.close());
```
Until the backend is ready, build against a mock array of events copied from `GET /runs/<id>/events`.

## Step 6: Memory and syllabus polish (hours 6-14, Sakshi)
1. Replace the 8 seed problems in `memory.py` with your own 20-30 (title, topic, difficulty 1-3, `error_types` tags).
2. Extend `tools.select_problems`: keep the DB choice as the fallback; optionally use `llm_json("select", ...)` for richer reasons, but only accept ids from the candidate list.
3. Add `POST /reviews/{id}/grade` in `main.py` calling `memory.grade_review(id, quality)` (already written in `memory.py`).
4. Define mastered in the demo: score below 0.1 and last two reviews graded 4+ (`sm2.is_mastered`).

## Step 7: Reliability layer (hours 14-18, whole team)
1. Keep `USE_CACHE=1` as the **demo fallback**. If Wi-Fi or the API dies, set it and the three demo students still work with the same UI.
2. Keep the `ScriptedDriver` path (`live: false`) as a second fallback: same tools, same trace.
3. Pre-run live mode for A, B and C and note the results; record a backup video of a clean run.
4. Add a visible "Live Gemini" vs "Cached demo" badge in the UI. Be honest with judges about which mode is running.

## Step 8: Freeze, rehearse, submit (hours 16-24)
- Hour 16: feature freeze. Only bug fixes after.
- Hours 20-23: rehearse the 2-minute demo three times, one person driving and one narrating.
- Replace wireframes in the deck with real screenshots; fix the NA fields (team name, what didn't work, demo evidence, links).
- Hour 23: tag the repo, test a fresh clone on a second laptop with `06_windows_setup.md`.

## Suggested hourly checkpoints
| Hour | Check |
|---|---|
| 1 | Everyone's environment works; `py test_agent.py` passes on Windows |
| 3 | Gemini key works; `llm_json('classify')` returns a valid label |
| 6 | **`py agent.py A --live` reaches conclusive** (the key milestone) |
| 9 | UI shows trace and the prediction gate against the real API |
| 12 | A, B, C all work live; result chart and diff shown |
| 16 | Syllabus, SM-2, failure handling done; freeze |
| 20 | Real screenshots and backup video done |

## Common problems
| Symptom | Fix |
|---|---|
| Runs fine but nothing is live | `GEMINI_API_KEY` empty, so it is in cache mode; check `.env` is loaded and you are in `backend\` |
| `404 model not found` | Set `GEMINI_MODEL` to one your key supports |
| JSON parse error from the model | Strip ``` fences, add `response_schema`, lower temperature |
| Mutation changes output | Tighten the `mutate` prompt; the retry loop handles it; check `outputs_equal` |
| Model keeps calling tools in a loop | Step cap stops at 12; make tool errors more specific |
| Model pastes huge code in arguments | Don't: tools take only `hypothesis` and `metric_name`; re-read the tool descriptions |
| SSE hangs on Windows | Run `uvicorn main:app` without `--reload`; use `127.0.0.1` |
| Sandbox prints nothing | Student code must print `__METRIC__ <n>` as its last line |
| Port in use | `netstat -ano \| findstr :8000` then `taskkill /PID <pid> /F` |
