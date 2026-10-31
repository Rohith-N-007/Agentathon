"""SQLite memory: submissions, fingerprint, reviews, experiments, trace, problems."""
import json
import os
import sqlite3
from datetime import date

import sm2

DB_PATH = os.environ.get("DB_PATH", "coach.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY, user_id TEXT, problem_id TEXT, language TEXT,
  code TEXT, verdict TEXT, failing_case TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS fingerprint(user_id TEXT, error_type TEXT, score REAL DEFAULT 0,
  confirmed_count INTEGER DEFAULT 0, last_seen TEXT, PRIMARY KEY(user_id, error_type));
CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, user_id TEXT, error_type TEXT, problem_id TEXT,
  ease REAL DEFAULT 2.5, interval_days INTEGER DEFAULT 0, repetitions INTEGER DEFAULT 0, due_date TEXT);
CREATE TABLE IF NOT EXISTS experiments(id INTEGER PRIMARY KEY, submission_id INTEGER, hypothesis TEXT,
  error_type TEXT, code_a TEXT, code_b TEXT, test_input TEXT, metric TEXT, count_a INTEGER, count_b INTEGER,
  outputs_equal INTEGER, prediction TEXT, conclusive INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS trace(id INTEGER PRIMARY KEY, submission_id INTEGER, step INTEGER, kind TEXT,
  tool TEXT, payload TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS problems(id TEXT PRIMARY KEY, title TEXT, topic TEXT, difficulty INTEGER,
  error_types TEXT, statement TEXT);
"""

SEED_PROBLEMS = [
    ("p1", "Number of Islands", "graphs", 2, "state-commit-timing,coverage-completeness"),
    ("p2", "Course Schedule", "graphs", 2, "ordering,coverage-completeness"),
    ("p3", "Word Ladder", "graphs", 3, "state-commit-timing"),
    ("p4", "Two Sum", "hashing", 1, "structure-selection"),
    ("p5", "Longest Consecutive Sequence", "hashing", 2, "structure-selection,boundary"),
    ("p6", "Merge Intervals", "sorting", 2, "ordering,boundary"),
    ("p7", "Search Insert Position", "binary search", 1, "boundary"),
    ("p8", "Connected Components in an Undirected Graph", "graphs", 2, "coverage-completeness"),
]


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        if c.execute("SELECT COUNT(*) FROM problems").fetchone()[0] == 0:
            c.executemany("INSERT INTO problems(id,title,topic,difficulty,error_types,statement) VALUES (?,?,?,?,?,'')",
                          SEED_PROBLEMS)


def add_submission(user_id, problem_id, language, code, verdict, failing_case=""):
    with conn() as c:
        cur = c.execute("INSERT INTO submissions(user_id,problem_id,language,code,verdict,failing_case) VALUES (?,?,?,?,?,?)",
                        (user_id, problem_id, language, code, verdict, failing_case))
        return cur.lastrowid


def log_trace(submission_id, step, kind, tool, payload):
    with conn() as c:
        c.execute("INSERT INTO trace(submission_id,step,kind,tool,payload) VALUES (?,?,?,?,?)",
                  (submission_id, step, kind, tool, json.dumps(payload, default=str)[:20000]))


def get_fingerprint(user_id):
    with conn() as c:
        rows = c.execute("SELECT error_type, score FROM fingerprint WHERE user_id=?", (user_id,)).fetchall()
    return {r["error_type"]: round(r["score"], 3) for r in rows}


def due_reviews(user_id):
    today = date.today().isoformat()
    with conn() as c:
        rows = c.execute("SELECT * FROM reviews WHERE user_id=? AND due_date<=? ORDER BY due_date", (user_id, today)).fetchall()
    return [dict(r) for r in rows]


def save_experiment(submission_id, hypothesis, error_type, state, result, prediction):
    with conn() as c:
        cur = c.execute(
            "INSERT INTO experiments(submission_id,hypothesis,error_type,code_a,code_b,test_input,metric,count_a,count_b,"
            "outputs_equal,prediction,conclusive) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (submission_id, hypothesis, error_type, state.get("code_a"), state.get("code_b"), state.get("test_input"),
             state.get("metric"), result.get("count_a"), result.get("count_b"), int(bool(result.get("outputs_equal"))),
             prediction, int(bool(result.get("conclusive")))))
        return cur.lastrowid


def update_fingerprint(user_id, error_type, problem_id=None):
    """Bump the score for a confirmed error and schedule its first review for tomorrow (SM-2)."""
    with conn() as c:
        row = c.execute("SELECT score, confirmed_count FROM fingerprint WHERE user_id=? AND error_type=?",
                        (user_id, error_type)).fetchone()
        score = sm2.bump_fingerprint(row["score"] if row else 0.0)
        count = (row["confirmed_count"] if row else 0) + 1
        c.execute("INSERT INTO fingerprint(user_id,error_type,score,confirmed_count,last_seen) VALUES (?,?,?,?,?) "
                  "ON CONFLICT(user_id,error_type) DO UPDATE SET score=excluded.score, "
                  "confirmed_count=excluded.confirmed_count, last_seen=excluded.last_seen",
                  (user_id, error_type, score, count, date.today().isoformat()))
        reps, interval, ease = sm2.sm2(3, 0, 0, 2.5)   # first review scheduled as if graded 3
        due = sm2.next_due(interval)
        c.execute("INSERT INTO reviews(user_id,error_type,problem_id,ease,interval_days,repetitions,due_date) VALUES (?,?,?,?,?,?,?)",
                  (user_id, error_type, problem_id, ease, interval, reps, due))
    return get_fingerprint(user_id), due


def grade_review(review_id, quality):
    with conn() as c:
        r = c.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        reps, interval, ease = sm2.sm2(quality, r["repetitions"], r["interval_days"], r["ease"])
        c.execute("UPDATE reviews SET repetitions=?, interval_days=?, ease=?, due_date=? WHERE id=?",
                  (reps, interval, ease, sm2.next_due(interval), review_id))
        if quality >= 4:   # clean solve: decay the fingerprint for this error type
            fp = c.execute("SELECT score FROM fingerprint WHERE user_id=? AND error_type=?",
                           (r["user_id"], r["error_type"])).fetchone()
            if fp:
                c.execute("UPDATE fingerprint SET score=? WHERE user_id=? AND error_type=?",
                          (sm2.decay_fingerprint(fp["score"]), r["user_id"], r["error_type"]))


def list_problems():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM problems").fetchall()]
