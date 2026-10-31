"""Sandbox runner for run_counterfactual (Windows-friendly, no Unix-only APIs).

Runs untrusted student code in a separate Python process with:
  - a wall-clock timeout (stops infinite loops),
  - a memory watchdog using psutil (kills the process tree if RSS goes over the limit),
  - stdin/stdout redirected via temp files (no pipe deadlocks, works the same on Windows).

Requires: pip install psutil
For stronger isolation on Windows, run the whole backend inside Docker Desktop (WSL2 backend)
with --network none. This module alone does NOT block file or network access.
"""
import difflib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import psutil

WALL_TIMEOUT = 4.0                      # seconds
MEMORY_LIMIT_BYTES = 256 * 1024 * 1024  # 256 MB resident memory
POLL_INTERVAL = 0.02
MAX_CHANGED_LINES = 6   # "one decision" can touch a few lines (e.g. move a commit from dequeue to enqueue)


def _kill_tree(proc: subprocess.Popen):
    try:
        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.Error:
                pass
        parent.kill()
    except psutil.Error:
        pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def run_code(code: str, stdin_text: str, metric_name: str):
    d = tempfile.mkdtemp(prefix="agentathon_")
    try:
        prog = os.path.join(d, "prog.py")
        inp = os.path.join(d, "in.txt")
        outp = os.path.join(d, "out.txt")
        errp = os.path.join(d, "err.txt")
        with open(prog, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        with open(inp, "w", encoding="utf-8", newline="\n") as f:
            f.write(stdin_text)

        status = "ok"
        with open(inp, "r", encoding="utf-8") as fin, \
             open(outp, "w", encoding="utf-8") as fout, \
             open(errp, "w", encoding="utf-8") as ferr:
            proc = subprocess.Popen(
                [sys.executable, "-I", prog],
                stdin=fin, stdout=fout, stderr=ferr, cwd=d,
            )
            start = time.monotonic()
            while proc.poll() is None:
                if time.monotonic() - start > WALL_TIMEOUT:
                    status = "timeout"
                    _kill_tree(proc)
                    break
                try:
                    if psutil.Process(proc.pid).memory_info().rss > MEMORY_LIMIT_BYTES:
                        status = "memory"
                        _kill_tree(proc)
                        break
                except psutil.Error:
                    pass
                time.sleep(POLL_INTERVAL)
            if status == "ok" and proc.returncode != 0:
                status = "error"
        # files are closed here, safe to read (and delete on Windows)

        with open(outp, "r", encoding="utf-8", errors="replace") as f:
            stdout = f.read()
        with open(errp, "r", encoding="utf-8", errors="replace") as f:
            stderr = f.read()

        out_lines, count = [], None
        for line in stdout.splitlines():
            if line.startswith("__METRIC__"):
                try:
                    count = int(line.split()[-1])
                except ValueError:
                    pass
            else:
                out_lines.append(line)
        return {"status": status, "output": "\n".join(out_lines).strip(),
                "count": count, "stderr": stderr[-500:]}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def changed_lines(a: str, b: str) -> int:
    """Number of lines changed, using a real diff so inserted lines don't shift everything."""
    la, lb = a.splitlines(), b.splitlines()
    sm = difflib.SequenceMatcher(None, la, lb)
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal")


def run_counterfactual(code_a: str, code_b: str, test_input: str, metric_name: str,
                       expected_output: str = None):
    """expected_output (optional): if given, use the coverage rule: conclusive when A and B
    outputs differ and B matches the expected answer (for correctness-type errors)."""
    ra = run_code(code_a, test_input, metric_name)
    rb = run_code(code_b, test_input, metric_name)
    outputs_equal = ra["output"] == rb["output"] and ra["status"] == rb["status"] == "ok"
    ca, cb = ra["count"], rb["count"]
    measurable = ca is not None and cb is not None
    diff_ok = measurable and abs(ca - cb) >= max(5, 0.2 * max(ca, cb, 1))
    small_change = changed_lines(code_a, code_b) <= MAX_CHANGED_LINES
    if expected_output is not None:
        conclusive = bool(ra["status"] == rb["status"] == "ok" and ra["output"] != rb["output"]
                          and rb["output"] == expected_output.strip())
    else:
        conclusive = bool(outputs_equal and diff_ok and small_change)
    return {
        "count_a": ca, "count_b": cb, "outputs_equal": outputs_equal,
        "status_a": ra["status"], "status_b": rb["status"],
        "stderr_a": ra["stderr"], "stderr_b": rb["stderr"],
        "conclusive": conclusive,
    }


if __name__ == "__main__":
    from demo_cases import STUDENT_A_A, STUDENT_A_B, DEMO_INPUT
    print(json.dumps(run_counterfactual(STUDENT_A_A, STUDENT_A_B, DEMO_INPUT, "pushes"), indent=2))
