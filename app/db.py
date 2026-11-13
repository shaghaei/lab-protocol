"""SQLite storage. Values are locked on submit: there is no update path."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .calc import Titration
from .synthetic import generate

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "lab.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL,
    group_code TEXT NOT NULL,
    station INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE (experiment_id, group_code)
);
CREATE TABLE IF NOT EXISTS titrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    idx INTEGER NOT NULL,
    mass_g REAL NOT NULL,
    start_ml REAL NOT NULL,
    end_ml REAL NOT NULL
);
"""


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = path or os.environ.get("LAB_DB", DEFAULT_PATH)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def group_exists(conn, experiment_id: str, group_code: str) -> bool:
    row = conn.execute("SELECT 1 FROM submissions WHERE experiment_id=? AND group_code=?",
                       (experiment_id, group_code)).fetchone()
    return row is not None


def insert_submission(conn, experiment_id: str, group_code: str, station: int,
                      titrations: list, source: str = "manual") -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO submissions (experiment_id, group_code, station, submitted_at, source) "
        "VALUES (?, ?, ?, ?, ?)", (experiment_id, group_code, station, now, source))
    sid = cur.lastrowid
    conn.executemany(
        "INSERT INTO titrations (submission_id, idx, mass_g, start_ml, end_ml) VALUES (?, ?, ?, ?, ?)",
        [(sid, i, t.mass_g, t.start_ml, t.end_ml) for i, t in enumerate(titrations, start=1)])
    conn.commit()
    return sid


def _with_titrations(conn, row) -> dict:
    ts = conn.execute("SELECT mass_g, start_ml, end_ml FROM titrations WHERE submission_id=? "
                      "ORDER BY idx", (row["id"],)).fetchall()
    d = dict(row)
    d["titrations"] = [Titration(t["mass_g"], t["start_ml"], t["end_ml"]) for t in ts]
    return d


def get_submission(conn, sid: int) -> dict | None:
    row = conn.execute("SELECT * FROM submissions WHERE id=?", (sid,)).fetchone()
    return _with_titrations(conn, row) if row else None


def list_submissions(conn, experiment_id: str) -> list:
    rows = conn.execute("SELECT * FROM submissions WHERE experiment_id=? ORDER BY group_code",
                        (experiment_id,)).fetchall()
    return [_with_titrations(conn, r) for r in rows]


def seed_if_empty(conn, experiment_id: str) -> int:
    """Load the synthetic class once, so the demo has a class to compare against."""
    count = conn.execute("SELECT COUNT(*) FROM submissions WHERE experiment_id=?",
                         (experiment_id,)).fetchone()[0]
    if count:
        return 0
    groups = generate()
    for g in groups:
        insert_submission(conn, experiment_id, g["code"], g["station"],
                          [Titration(*t) for t in g["titrations"]], source="synthetic")
    return len(groups)
