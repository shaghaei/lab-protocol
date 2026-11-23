"""SQLite storage. Experiments are stored as JSON; submitted values are locked."""
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .experiments import BUILTINS, Experiment, from_dict
from .synthetic import generate

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "lab_v3.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    definition TEXT NOT NULL,
    builtin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL,
    step_id INTEGER NOT NULL DEFAULT 0,      -- 0 = open demo catalog, else a course step
    group_code TEXT NOT NULL,
    station INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE (experiment_id, step_id, group_code)
);
CREATE TABLE IF NOT EXISTS courses (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    n_groups INTEGER NOT NULL,
    stations INTEGER NOT NULL,
    teacher_hash TEXT NOT NULL,
    class_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT NOT NULL,
    position INTEGER NOT NULL,
    experiment_id TEXT NOT NULL,
    title TEXT NOT NULL,
    groups TEXT NOT NULL,                    -- JSON list of group codes
    links TEXT NOT NULL                      -- JSON {quantity key: source step id}
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    idx INTEGER NOT NULL,
    vals TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = path or os.environ.get("LAB_DB", DEFAULT_PATH)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# experiments ---------------------------------------------------------------

def save_experiment(conn, exp: Experiment) -> None:
    conn.execute("INSERT OR REPLACE INTO experiments (id, definition, builtin, created_at) "
                 "VALUES (?, ?, ?, ?)", (exp.id, json.dumps(exp.to_dict()), int(exp.builtin), now()))
    conn.commit()


def list_experiments(conn) -> list:
    """Built-in experiments come from code, so updates to them apply at once."""
    rows = conn.execute("SELECT definition FROM experiments WHERE builtin=0 ORDER BY created_at")
    return list(BUILTINS) + [from_dict(json.loads(r["definition"])) for r in rows]


def get_experiment(conn, eid: str) -> Experiment | None:
    for exp in BUILTINS:
        if exp.id == eid:
            return exp
    row = conn.execute("SELECT definition FROM experiments WHERE id=?", (eid,)).fetchone()
    return from_dict(json.loads(row["definition"])) if row else None


def delete_experiment(conn, eid: str) -> None:
    sids = [r["id"] for r in conn.execute("SELECT id FROM submissions WHERE experiment_id=?", (eid,))]
    conn.executemany("DELETE FROM runs WHERE submission_id=?", [(s,) for s in sids])
    conn.execute("DELETE FROM submissions WHERE experiment_id=?", (eid,))
    conn.execute("DELETE FROM experiments WHERE id=? AND builtin=0", (eid,))
    conn.commit()


def unique_id(conn, title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "experiment"
    eid, n = base, 2
    taken = {e.id for e in BUILTINS}
    while eid in taken or conn.execute("SELECT 1 FROM experiments WHERE id=?", (eid,)).fetchone():
        eid, n = f"{base}-{n}", n + 1
    return eid


# submissions ---------------------------------------------------------------

def group_exists(conn, experiment_id: str, group_code: str, step_id: int = 0) -> bool:
    return conn.execute("SELECT 1 FROM submissions WHERE experiment_id=? AND step_id=? AND group_code=?",
                        (experiment_id, step_id, group_code)).fetchone() is not None


def insert_submission(conn, experiment_id: str, group_code: str, station: int, runs: list,
                      source: str = "manual", step_id: int = 0) -> int:
    cur = conn.execute("INSERT INTO submissions (experiment_id, step_id, group_code, station, "
                       "submitted_at, source) VALUES (?, ?, ?, ?, ?, ?)",
                       (experiment_id, step_id, group_code, station, now(), source))
    sid = cur.lastrowid
    conn.executemany("INSERT INTO runs (submission_id, idx, vals) VALUES (?, ?, ?)",
                     [(sid, i, json.dumps(v)) for i, v in enumerate(runs, start=1)])
    conn.commit()
    return sid


def _with_runs(conn, row) -> dict:
    rs = conn.execute("SELECT vals FROM runs WHERE submission_id=? ORDER BY idx", (row["id"],))
    d = dict(row)
    d["runs"] = [json.loads(r["vals"]) for r in rs]
    return d


def get_submission(conn, sid: int) -> dict | None:
    row = conn.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
    return _with_runs(conn, row) if row else None


def list_submissions(conn, experiment_id: str, step_id: int = 0) -> list:
    rows = conn.execute("SELECT * FROM submissions WHERE experiment_id=? AND step_id=? ORDER BY group_code",
                        (experiment_id, step_id)).fetchall()
    return [_with_runs(conn, r) for r in rows]


def delete_submission(conn, sid: int) -> None:
    conn.execute("DELETE FROM runs WHERE submission_id=?", (sid,))
    conn.execute("DELETE FROM submissions WHERE id=?", (sid,))
    conn.commit()


def count_submissions(conn) -> dict:
    """Counts in the open catalog only (course data stays inside its course)."""
    rows = conn.execute("SELECT experiment_id, COUNT(*) AS n FROM submissions WHERE step_id=0 "
                        "GROUP BY experiment_id")
    return {r["experiment_id"]: r["n"] for r in rows}


# courses and steps -----------------------------------------------------------

def group_codes(n: int) -> list:
    return [f"G{i:02d}" for i in range(1, n + 1)]


def new_course_code(conn, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "course"
    while True:
        code = f"{base}-{secrets.token_hex(2)}"
        if not get_course(conn, code):
            return code


def create_course(conn, code: str, name: str, n_groups: int, stations: int,
                  teacher_hash: str, class_hash: str) -> None:
    conn.execute("INSERT INTO courses (code, name, n_groups, stations, teacher_hash, class_hash, "
                 "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (code, name, n_groups, stations, teacher_hash, class_hash, now()))
    conn.commit()


def get_course(conn, code: str) -> dict | None:
    row = conn.execute("SELECT * FROM courses WHERE code=?", (code,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["groups"] = group_codes(d["n_groups"])
    return d


def _step(row) -> dict:
    d = dict(row)
    d["groups"] = json.loads(d["groups"])
    d["links"] = {k: int(v) for k, v in json.loads(d["links"]).items()}
    return d


def list_steps(conn, code: str) -> list:
    rows = conn.execute("SELECT * FROM steps WHERE course_code=? ORDER BY position", (code,))
    return [_step(r) for r in rows]


def get_step(conn, step_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM steps WHERE id=?", (step_id,)).fetchone()
    return _step(row) if row else None


def add_step(conn, code: str, experiment_id: str, title: str, groups: list, links: dict) -> int:
    pos = conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM steps WHERE course_code=?",
                       (code,)).fetchone()[0]
    cur = conn.execute("INSERT INTO steps (course_code, position, experiment_id, title, groups, links) "
                       "VALUES (?, ?, ?, ?, ?, ?)",
                       (code, pos, experiment_id, title, json.dumps(groups), json.dumps(links)))
    conn.commit()
    return cur.lastrowid


def delete_step(conn, step_id: int) -> None:
    for (sid,) in conn.execute("SELECT id FROM submissions WHERE step_id=?", (step_id,)).fetchall():
        conn.execute("DELETE FROM runs WHERE submission_id=?", (sid,))
    conn.execute("DELETE FROM submissions WHERE step_id=?", (step_id,))
    conn.execute("DELETE FROM steps WHERE id=?", (step_id,))
    conn.commit()


def seed(conn) -> None:
    """Load the synthetic class of each built-in experiment once, and the demo course."""
    counts = count_submissions(conn)
    for exp in BUILTINS:
        if not counts.get(exp.id):
            for g in generate(exp):
                insert_submission(conn, exp.id, g["code"], g["station"], g["runs"], source="synthetic")
    from .demo_course import seed_demo_course
    seed_demo_course(conn)
