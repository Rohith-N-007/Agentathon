# Windows Setup (do this in hour 0-1, everyone)

All instructions assume Windows 10/11 and PowerShell. Nothing in this kit needs WSL or Linux.

## 1. Install
| Tool | Get it | Check |
|---|---|---|
| Python 3.10+ | python.org (tick "Add python.exe to PATH") | `py --version` |
| Node.js 18+ LTS | nodejs.org | `node --version`, `npm --version` |
| Git | git-scm.com | `git --version` |
| (optional) Docker Desktop | docker.com, WSL2 backend | only for the stretch-goal sandbox hardening |

## 2. Get the code
```powershell
git clone <your-repo-url>
cd <repo>
git config core.autocrlf true      # avoid CRLF/LF noise between teammates
```
Add a `.gitattributes` with `*.py text eol=lf` if diffs look noisy.

## 3. Backend environment
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install fastapi uvicorn google-genai python-dotenv psutil
```
If activation is blocked: `Set-ExecutionPolicy -Scope Process Bypass` and retry (affects this window only).

## 4. Environment variables
```powershell
copy ..\.env.example .env
notepad .env       # GEMINI_API_KEY=your_key (never commit .env; add it to .gitignore)
```

## 5. Run
```powershell
uvicorn main:app --reload                 # backend on http://127.0.0.1:8000
cd ..\frontend; npm install; npm run dev  # frontend on http://localhost:3000
```
Allow Python through Windows Defender Firewall if prompted (private networks only).

## 6. Sanity tests (Rohit, first thing)
```powershell
py sandbox.py        # expect count_a 781, count_b 40, conclusive true
py sm2.py
```
Also test the limits:
```powershell
py -c "from sandbox import run_code; print(run_code('while True: pass','','x')['status'])"        # timeout
py -c "from sandbox import run_code; print(run_code('x = bytearray(10**9)','','x')['status'])"   # memory or error
```

## 7. Windows gotchas
- Use `py` (launcher) or `python`; not `python3`.
- Paths use backslashes in PowerShell; in Python use `os.path.join` or `pathlib`, never hardcode `/tmp`.
- Always open files with `encoding="utf-8"`; Windows defaults can break on non-ASCII characters.
- Port already in use: `netstat -ano | findstr :8000` then `taskkill /PID <pid> /F`.
- Long paths or OneDrive folders can lock files; keep the repo in `C:\dev\`, not inside OneDrive.
- Antivirus can slow down subprocess starts; if the sandbox feels slow, exclude the repo folder.
- On Windows, `uvicorn --reload` plus subprocesses is fine, but if SSE hangs use `uvicorn main:app` without `--reload` for the demo.
- Sandbox isolation: no file or network blocking, so only run the demo cases and student code from trusted users.
