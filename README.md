# Why-Did-I-Fail Coach (Agentathon 2026, Education track)

An AI coach that finds the reasoning mistake behind a failed coding submission, **proves it by running a counterfactual experiment** in a sandbox, remembers it, and plans targeted practice.

> Other tools tell you what you got wrong. Ours shows you why, by running the experiment.

Team (PES University): Sakshi, Samhita, Rohit, Saanvi

## How it works
1. Paste a failed submission (or pick demo Student A, B or C).
2. The agent classifies the error and forms hypotheses.
3. It mutates ONE decision in the code and generates a tricky input.
4. You predict the effect; the sandbox runs both versions and measures it.
5. A conclusive result updates your weakness fingerprint and schedules a spaced review (SM-2).
6. A daily syllabus gives each problem a reason.

## Repo layout
```
agentathon-coach/
  README.md
  .gitignore  .gitattributes
  backend/
    main.py          FastAPI app: runs, prediction gate, events, SSE, fingerprint
    agent.py         the agent loop (step cap, hard rules, trace)
    llm.py           prompts, Gemini driver, scripted fallback driver, cached demo answers
    tools.py         the 8 tools + Gemini tool declarations
    sandbox.py       run_counterfactual (timeout + psutil memory watchdog, Windows-friendly)
    memory.py        SQLite: fingerprint, reviews, experiments, trace, problem bank
    sm2.py           spaced repetition + fingerprint rules
    demo_cases.py    cached demo students A, B, C
    test_agent.py    offline tests
    requirements.txt
    .env.example
  docs/
    01_first_review_pitch.md      pitch script, Q&A, deck fixes
    02_architecture_and_api.md    design, schema, conclusive rules
    03_tool_schemas.json          design-time tool contract (backend/tools.py wins)
    04_prompts.md                 prompt designs
    06_windows_setup.md           Windows setup
    07_build_guide.md             step-by-step build guide
    08_split_four_people.md       who does what until 09:00
    frontend/                     API contract + mock data for the UI
  frontend/                       (created by Saanvi: `npx create-next-app@latest frontend`)
```

## Quick start (Windows 10/11, PowerShell)
Prerequisites: Python 3.10+ ("Add to PATH"), Node.js 18+ LTS, Git. Details in `docs/06_windows_setup.md`.
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
copy .env.example .env             # add GEMINI_API_KEY for live mode
py test_agent.py                   # expect: ALL OK
py agent.py A                      # CLI demo (cached); type "fewer" at the prediction gate
uvicorn main:app --reload          # API on http://127.0.0.1:8000  (docs at /docs)
```
Frontend (Saanvi creates it, then everyone):
```powershell
cd frontend
npm install
npm run dev                        # http://localhost:3000
```

## Two modes (the UI should always show which one is running)
| Mode | When | What it does |
|---|---|---|
| **Cached demo** | `GEMINI_API_KEY` empty, or `USE_CACHE=1` | Recorded LLM answers for Students A, B, C; sandbox and memory are real. Works offline. |
| **Live Gemini** | `GEMINI_API_KEY` set and `live: true` in `POST /runs` | Gemini picks tools via function calling and writes mutations. Test it with `py agent.py A --live`. |

An empty key silently selects cached mode, so check which one you are in.

## Safety
Code runs in a separate process with a wall-clock timeout and a memory watchdog. This does not block file or network access, so never expose it publicly as is. For stronger isolation run it inside Docker Desktop (WSL2 backend) with `--network none`.

## Limitations
Python only; paste-in submissions; one problem family in the demo; the 15-student survey is a small peer sample and not representative. Live Gemini mode needs prompt tuning (see `docs/07_build_guide.md`, step 3).
