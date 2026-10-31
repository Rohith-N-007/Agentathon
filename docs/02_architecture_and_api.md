# Architecture, API and Data Model

## System overview
```
Next.js UI  <--REST + SSE-->  FastAPI backend
                                 |-- Agent loop (Gemini function calling, max 12 steps)
                                 |-- Tools: classify_failure, mutate_code, generate_test_input,
                                 |          request_prediction, run_counterfactual, select_problems
                                 |-- Sandbox (subprocess + memory watchdog + timeout)
                                 `-- SQLite (submissions, fingerprint, reviews, experiments, trace)
```

## Agent loop (pseudocode)
```python
MAX_STEPS = 12
def run_agent(submission_id):
    state = load_state(submission_id)            # includes fingerprint + review queue
    history = [system_prompt, user_message(state)]
    for step in range(MAX_STEPS):
        resp = gemini.generate(history, tools=TOOL_SCHEMAS)
        if resp.has_function_call:
            name, args = resp.function_call
            log_trace(submission_id, step, "call", name, args)
            result = TOOLS[name](**args)          # deterministic or LLM-backed
            log_trace(submission_id, step, "result", name, result)
            history += [resp, function_response(name, result)]
            if name == "request_prediction":      # pauses until UI posts the user's guess
                result = wait_for_prediction(submission_id)
        else:
            log_trace(submission_id, step, "final", None, resp.text)
            break
```

Hard rules enforced in code (not only in the prompt):
- `update_memory` is only allowed after a conclusive `run_counterfactual`.
- Max 2 retries of `mutate_code` per hypothesis, then the next hypothesis, then abstain.
- Every tool result is logged to `trace`.

## Conclusive experiment definition
An experiment is conclusive when ALL are true:
1. A and A′ both compile and finish within limits.
2. Outputs of A and A′ are identical on the test input (behaviour preserved).
3. The measured metric differs by at least 20% (or at least 5 ops absolute).
4. The diff between A and A′ is at most 6 changed lines (one decision can touch a few lines).

For correctness-type errors (e.g. coverage-completeness) the rule is different: A and B outputs differ and B matches the expected answer (`expected_output`), still with a small diff.

## REST endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/submissions` | Body: `{problem_id, language, code, verdict, failing_case?}`; creates submission |
| POST | `/submissions/{id}/analyze` | Starts the agent run; returns `run_id` |
| GET | `/runs/{run_id}/stream` | SSE: trace events (call/result/final/prediction_request) |
| POST | `/runs/{run_id}/prediction` | Body: `{guess: "more"|"fewer"|"same"}` |
| GET | `/runs/{run_id}/result` | Experiment result: A/A′ counts, outputs, verdict, diff |
| GET | `/fingerprint/{user_id}` | Scores per error type |
| GET | `/syllabus/{user_id}` | Today's problems with reasons |
| POST | `/reviews/{id}/grade` | Body: `{quality: 0-5}`; updates SM-2 |
| GET | `/demo/{student}` | Loads cached demo case (A, B or C) |

## SQLite schema
```sql
CREATE TABLE submissions(id INTEGER PRIMARY KEY, user_id TEXT, problem_id TEXT, language TEXT,
  code TEXT, verdict TEXT, failing_case TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE fingerprint(user_id TEXT, error_type TEXT, score REAL DEFAULT 0,
  confirmed_count INTEGER DEFAULT 0, last_seen TEXT, PRIMARY KEY(user_id, error_type));

CREATE TABLE reviews(id INTEGER PRIMARY KEY, user_id TEXT, error_type TEXT, problem_id TEXT,
  ease REAL DEFAULT 2.5, interval_days INTEGER DEFAULT 0, repetitions INTEGER DEFAULT 0,
  due_date TEXT);

CREATE TABLE experiments(id INTEGER PRIMARY KEY, submission_id INTEGER, hypothesis TEXT,
  error_type TEXT, code_a TEXT, code_b TEXT, test_input TEXT, metric TEXT,
  count_a INTEGER, count_b INTEGER, outputs_equal INTEGER, prediction TEXT,
  conclusive INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE trace(id INTEGER PRIMARY KEY, submission_id INTEGER, step INTEGER, kind TEXT,
  tool TEXT, payload TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE problems(id TEXT PRIMARY KEY, title TEXT, topic TEXT, difficulty INTEGER,
  error_types TEXT, statement TEXT);  -- error_types: comma-separated tags
```

## Fingerprint score rule
- Confirmed error of type T: `score[T] = min(1.0, score[T] + 0.25)`.
- Clean, optimized solve on a problem tagged T: `score[T] *= 0.6`.
- Mastered: score below 0.1 and last two reviews graded 4 or higher.

## Error taxonomy (keep to these five for the demo)
| Type | Example |
|---|---|
| state-commit-timing | Marking visited on dequeue instead of enqueue |
| boundary | Off-by-one, empty input, n=1 |
| structure-selection | List for membership instead of set/dict |
| ordering | Wrong sort/traversal order |
| coverage-completeness | Missing disconnected components or cases |

## Sandbox design (Windows)
- Run each program in a fresh Python process (`sys.executable -I prog.py`); code and stdin go through temp files, stdout/stderr are redirected to temp files (no pipe deadlocks on Windows).
- Limits: wall-clock timeout (4 s) and a memory watchdog using `psutil` (kills the process tree if resident memory exceeds 256 MB). `resource.setrlimit` is Unix-only and is NOT used.
- Operation counting: `mutate_code` inserts a counter variable the hypothesis names (e.g. `pushes`), and the program prints `__METRIC__ <n>` as its last line. Fallback: line-event counting with `sys.settrace`.
- Compare stdout of A and A' to ensure behaviour is preserved.
- Isolation caveat: this does not block file or network access. For stronger isolation run the backend in Docker Desktop (WSL2 backend) with `--network none`, or use Windows Job Objects (stretch goal).
