# API contract for the frontend (Saanvi)

Backend: `http://127.0.0.1:8000` (use `127.0.0.1`, not `localhost`). CORS allows `http://localhost:3000`.
Interactive docs: `http://127.0.0.1:8000/docs`.

Mock data generated from real cached runs: `mock_run_A.json`, `mock_run_B.json`, `mock_run_C.json`. Each file has `{ events, result, fingerprint }`. Build the UI against these first, then switch to the live API.

## Flow
1. `POST /runs` to start. 2. Watch events (SSE or polling). 3. When an event has `kind: "prediction_request"`, show the gate and `POST /runs/{id}/prediction`. 4. When done, `GET /runs/{id}/result`. 5. `GET /fingerprint/{user_id}`.

## Endpoints that exist now
### `POST /runs`
Body (all optional except `student` OR `code`):
```json
{ "user_id": "demo", "student": "A", "problem": "...", "code": "...", "verdict": "Wrong Answer", "failing_case": "", "live": false }
```
`student` is "A", "B" or "C" (cached demo submissions). `live: true` lets Gemini drive the loop. Returns `{ "run_id": "ab12cd34" }`.

### `GET /runs/{run_id}/events?since=0` (polling)
Returns `{ "events": [...], "next": 18, "done": true, "error": null }`. Pass `since=<next>` on the next call.

### `GET /runs/{run_id}/stream` (SSE)
Each message is one event as JSON. A final `event: done` message carries `{ "error": null | "..." }`.
```js
const es = new EventSource(`http://127.0.0.1:8000/runs/${runId}/stream`);
es.onmessage = (m) => { const e = JSON.parse(m.data); /* handle e */ };
es.addEventListener("done", () => es.close());
```

### Event shape
```json
{ "step": 3, "kind": "call | result | final | prediction_request", "tool": "mutate_code", "payload": { } }
```
| kind | tool | payload |
|---|---|---|
| `call` | tool name | the arguments the agent passed |
| `result` | tool name | what the tool returned |
| `prediction_request` | `request_prediction` | `{ "question": "...", "options": ["more","fewer","same"] }` (step is -1) |
| `final` | null | the agent's closing text (string) |

Useful `result` payloads:
- `classify_failure`: `{ error_type, confidence, evidence }`
- `mutate_code`: `{ change_description, metric, versions_stored }`
- `run_counterfactual`: `{ count_a, count_b, outputs_equal, status_a, status_b, conclusive, prediction_correct }`
- `update_memory`: `{ fingerprint: { error_type: score }, next_review_date }`
- `select_problems`: `{ syllabus: [ { problem_id, title, reason, targets } ] }` (3 items)
- Any tool can return `{ "error": "..." }`; show it in the trace.

### `POST /runs/{run_id}/prediction`
Body `{ "guess": "more" | "fewer" | "same" }`. The paused run continues. If nobody answers within 120 s it continues with "no answer".

### `GET /runs/{run_id}/result` (after `done`)
```json
{ "result": {
    "final": "text", "error_type": "state-commit-timing", "conclusive": true, "prediction": "fewer",
    "experiment": { "count_a": 781, "count_b": 40, "outputs_equal": true, "status_a": "ok", "status_b": "ok",
                    "conclusive": true, "prediction_correct": true },
    "code_a": "...", "code_b": "..." },
  "error": null }
```
Use `count_a` / `count_b` for the A vs A′ bar chart and `code_a` / `code_b` for the diff. For Student C, `count_a` is null (it is a correctness fix, not an op-count race): show the outputs instead, or hide the chart and show "A: 1 component, expected 3".

### `GET /fingerprint/{user_id}`
`{ "state-commit-timing": 0.25 }`. Score is 0 to 1. Missing types mean 0. The five types: `state-commit-timing`, `boundary`, `structure-selection`, `ordering`, `coverage-completeness`.

### `GET /reviews/{user_id}`
List of reviews due today: `[ { id, user_id, error_type, problem_id, ease, interval_days, repetitions, due_date } ]`.

## Endpoints still to be added (agree the shapes with the owner)
| Route | Owner | Purpose |
|---|---|---|
| `GET /mode` | Rohit | `{ "mode": "live" | "cached" }` for the UI badge |
| `GET /syllabus/{user_id}` | Sakshi | today's 3 problems with reasons |
| `POST /reviews/{id}/grade` | Sakshi | body `{ "quality": 0-5 }` |
| `POST /demo/reset` | Sakshi | body `{ "user_id": "demo" }` clears that user's data so the demo can re-run |

Until those exist, take the syllabus from the `select_problems` result event and use cached mode as the default badge.

## Screens (from the deck wireframes)
1. **Fingerprint dashboard**: bars per error type from `/fingerprint`.
2. **Prediction gate**: A / A′ code panes, buttons More pushes / Fewer / Same.
3. **Result view**: bar chart of measured operations for A vs A′, same-output badge, "your prediction was correct/incorrect".
4. **Daily syllabus**: 3 problems, each with its reason.
Plus a live trace list, a student picker (A/B/C) and a mode badge. Deck colours: black background, orange (#F26B1D-ish) and green accents.
