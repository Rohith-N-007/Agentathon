# Work Split for Sakshi, Samhita, Rohit and Saanvi: finish by 09:00 (Sun 1 Nov)

Now: Sat 16:23. Deadline: Sun 09:00. That is about 16h30m.
Plan: **feature freeze at 03:00, submit by 08:30, 30-minute buffer.**
This replaces `08_split_three_people.md` (ignore that one).

## What is already done (do not rebuild)
Sandbox, agent loop, 8 tools, SQLite memory, SM-2, FastAPI (runs, prediction gate, events, SSE), cached demo mode for Students A/B/C, offline tests, docs. See `07_build_guide.md`.

## What is left
1. Make live Gemini work reliably (the riskiest part).
2. Build the UI (nothing exists yet).
3. Verify everything on Windows; harden the sandbox.
4. Problem bank, syllabus, demo reset.
5. Deck fixes, screenshots, demo video, submission.

## Roles
Four independent workstreams with separate files, so you won't collide in git. **The name mapping is a suggestion, swap freely.**

| Role | Person | Owns files | Mission |
|---|---|---|---|
| **1. AI and agent lead** | Samhita | `llm.py`, `tools.py`, `agent.py`, `04_prompts.md` | Live Gemini reaches a conclusive result for A, B and C, with retries and abstain |
| **2. Sandbox and backend reliability** | Rohit | `sandbox.py`, run routes in `main.py`, tests | Everything works on Windows; mutations are validated; fallbacks work |
| **3. Frontend** | Saanvi | `frontend/` | A UI that shows the loop clearly; real screenshots |
| **4. Memory, content and demo** | Sakshi | `memory.py`, `sm2.py`, data routes at the bottom of `main.py`, deck, README, pitch, video | Problem bank, syllabus, reviews, demo reset; deck, pitch, video, submission |

Rules: only edit your own files. Sakshi adds data routes at the **bottom** of `main.py` under a `# data routes` comment; Rohit owns the run routes above it. Commit small, pull before you push.

---

## Role 1: AI and agent lead (Samhita)

| Time | Task | Done when |
|---|---|---|
| 16:25-17:00 | Get the Gemini API key. Check the model name. Test `llm_json('classify')` live (guide step 3) | Student A returns `state-commit-timing` |
| 17:00-18:30 | Live `mutate` and `test_input` for A. Feed results into `sandbox.run_counterfactual`. Fix prompts | A and B versions run, same output, different count |
| 18:30-20:00 | Full live loop: `py agent.py A --live` | **Conclusive 3 runs out of 3 (checkpoint 20:00)** |
| 20:00-22:30 | Same for Student B and Student C | All three conclusive live |
| 22:30-00:30 | Failure handling: use the `reason` field from Rohit, switch hypothesis after 2 retries, abstain message, tests for each path | `py test_agent.py` covers inconclusive and abstain |
| 00:30-02:00 | Hardening: run each student 5 times live and note the success rate. Fix the worst prompt. Save one good run each | Success rate known per student |
| 02:00-03:00 | Give Sakshi the "What didn't work" text from your failure log | 3 real learnings handed over |

**Keep a running log of every failure** (bad mutation, malformed JSON, wrong label). It becomes the "What didn't work" slide.

## Role 2: Sandbox and backend reliability (Rohit)

| Time | Task | Done when |
|---|---|---|
| 16:25-17:00 | **Create the GitHub repo and push the kit first** so the others can clone. Run `py sandbox.py` and `py test_agent.py` on Windows. Fix any Windows issue | Both pass on Windows; repo link shared |
| 17:00-18:30 | Test the API on Windows including SSE. Add a `reason` field to `run_counterfactual` when not conclusive (outputs differ / no measurable difference / timeout / memory). Tell Samhita | Each inconclusive case returns a clear reason |
| 18:30-21:00 | Add `validate_mutation()` in `sandbox.py`: both versions compile, diff is at most 6 lines, the metric line is printed. Add tests: timeout, memory, crash, huge output, Student C rule, CRLF input | Bad mutations are caught before they run |
| 21:00-23:00 | Add `GET /mode` (live or cached, for the UI badge). Help Samhita debug live runs (this is the riskiest area) | Badge endpoint works; live bugs shrinking |
| 23:00-01:00 | Reliability: error handling and logging every live run to a file (so Samhita can compute success rates). Cached fallback works with Wi-Fi off | Demo works in cached mode with Wi-Fi off |
| 01:00-03:00 | Help whichever of Samhita, Saanvi or Sakshi is behind | Their blockers cleared |

## Role 3: Frontend (Saanvi)

Use the real backend from the start: run it in cached mode on your own laptop (`uvicorn main:app`), no waiting for the others.

| Time | Task | Done when |
|---|---|---|
| 16:25-17:30 | Next.js app, run the backend locally, student picker (A/B/C), start a run, show the event list (polling `GET /runs/{id}/events` is fine to start) | You can start Student A and see trace events |
| 17:30-19:30 | Prediction gate (More / Fewer / Same buttons posting to `/runs/{id}/prediction`), switch to SSE | The gate appears mid-run and the run continues |
| 19:30-21:30 | Result view: bar chart A vs A′, diff of `code_a` and `code_b` (Monaco diff, or two code blocks if short on time), "your prediction was correct" | Result screen matches wireframe 3 |
| 21:30-23:30 | Fingerprint dashboard (bars per error type), syllabus with reasons (from Sakshi's endpoint), mode badge "Live Gemini / Cached demo" | Wireframes 1 and 4 done |
| 23:30-01:30 | Polish: loading and error states, deck colours (black, orange, green) | Looks clean on a projector |
| 01:30-03:00 | Real screenshots of all four screens, send to Sakshi; help record the video | Screenshots saved and shared |

## Role 4: Memory, content and demo (Sakshi)

| Time | Task | Done when |
|---|---|---|
| 16:25-17:15 | Read `07_build_guide.md` and `memory.py`. Get your environment working (`06_windows_setup.md`), run `py test_agent.py` and `py agent.py A` | Tests pass on your laptop |
| 17:15-19:30 | **Problem bank:** 20-30 problems in `memory.py`, each with title, topic, difficulty 1-3 and error-type tags. At least 3 per error type | Every error type has 3 or more problems |
| 19:30-21:30 | Data routes at the bottom of `main.py`: `GET /syllabus/{user_id}`, `POST /reviews/{id}/grade` (uses `memory.grade_review`), `POST /demo/reset` (clear a user's data so the demo can be re-run). Use `sm2.is_mastered` for "mastered". Tell Saanvi the response shapes | Endpoints work; Saanvi told |
| 21:30-23:30 | Deck work: tech stack slide, references slide, team name, README. Write the pitch script and Q&A cards from `01_first_review_pitch.md` | Deck text fixes done except screenshots and "What didn't work" |
| 23:30-01:30 | Write the demo script. Rehearse it against the UI as Saanvi finishes screens (find confusing parts and tell her) | One rehearsal done, UI feedback sent |
| 01:30-03:00 | Record the backup demo video (Win+G or OBS), trim it, upload it, get the link | Video link ready |

---

## Sync points (5 minutes each, standing)
18:00, **20:00 checkpoint**, 22:00, 00:00, 02:00, 03:00 freeze.

**20:00 checkpoint:** Student A conclusive live, and the UI shows trace plus gate against the real API. If live Gemini is not working by 20:00, Rohit helps Samhita until 22:00. If it still fails at 22:00, **demo in cached mode and say so honestly** (show the badge, explain the loop is the same code with recorded LLM answers). Don't hide it from judges.

## After the freeze (03:00-09:00)

Two pairs sleep in turn, so someone is always working.

| Time | Samhita + Rohit | Sakshi + Saanvi |
|---|---|---|
| 03:00-03:30 | Fresh-clone test together on one laptop: clone, install, run, demo all three students | same |
| 03:30-06:00 | Sleep | Real screenshots into the deck, "What didn't work", links, final deck pass |
| 06:00-07:00 | Final live-mode check on all three students; pick cached or live for the demo | Sleep (until 07:00) |
| 07:00-08:00 | Everyone: rehearse the 2-minute demo 3 times, then fix only critical bugs | |
| 08:00-08:30 | **Submit** (deck, repo link, video link) | |
| 08:30-09:00 | Buffer | |

Staying up all night makes demos worse. Take the sleep blocks, even short ones.

## Deck fixes (Sakshi owns them)
1. Team name (blank).
2. "What didn't work": replace NA with 3 real learnings (from Samhita).
3. Demo evidence and Links: replace NA with the repo link and video link.
4. Replace the wireframes with real screenshots (from Saanvi).
5. Tech stack slide: change "subprocess with CPU/memory limits" to "subprocess with timeout and psutil memory watchdog".
6. References slide: replace the Python `resource` module link with psutil (psutil.readthedocs.io).
7. **Team members slide:** it lists Ramya R, Sai Vamshi B V, Killi Sai Lohith and Sakshi Rajendra Kage. If your registered team is Sakshi, Samhita, Rohit and Saanvi, check the organisers' rules before changing names.

## If you fall behind: cut in this order
1. LLM-written syllabus reasons (keep the database-based ones).
2. Review grading and mastered logic in the UI.
3. Monaco diff (use two code blocks).
4. SSE (use polling).
5. Problem bank beyond about 12 problems.
6. Live mode for Student C (show B and C in cached mode).

**Never cut:** the full loop for Student A, the prediction gate, the A vs A′ result chart, the fingerprint dashboard, and the backup video.

## 2-minute demo (rehearse by 07:00)
1. "Three students fail the same graph problem for three different reasons."
2. Run Student A. Show the trace: classification, hypothesis, mutation.
3. Prediction gate: pick More / Fewer / Same.
4. Result chart: measured pushes, same output.
5. Fingerprint updates and syllabus shows a reason per problem.
6. Run B and C: different diagnoses from the same problem.
7. Close: "Other tools tell you what you got wrong. Ours shows you why, by running the experiment."
