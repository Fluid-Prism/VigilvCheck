"""store.py — local SQLite for posture history.

Same discipline as Kevscope's store.py: WAL mode, owner-only file
permissions. This one's purpose is narrower — it just remembers what each
scan found, so "posture over time" has something real to show instead of
only ever displaying the latest run.
"""
import os
import sqlite3
import threading
import time

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vigilvcheck.db")
_lock = threading.Lock()


def conn():
    c = sqlite3.connect(DB_PATH, timeout=20)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init():
    with _lock, conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS scan(
              ts INTEGER PRIMARY KEY,
              score INTEGER,              -- NULL if nothing was applicable that run
              applicable_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS result(
              ts        INTEGER NOT NULL,
              check_id  TEXT NOT NULL,
              status    TEXT NOT NULL,
              detail    TEXT NOT NULL,
              PRIMARY KEY (ts, check_id)
            );
            CREATE INDEX IF NOT EXISTS idx_result_check ON result(check_id, ts);
            """
        )
    # This DB holds a record of exactly which hardening basics this machine
    # fails and why — not something to leave world-readable.
    try:
        os.chmod(DB_PATH, 0o600)
    except OSError:
        pass


def record_scan(results, score, applicable_count):
    """results: [(check, CheckResult), ...]. Returns the scan timestamp."""
    ts = int(time.time())
    with _lock, conn() as c:
        c.execute("INSERT INTO scan(ts, score, applicable_count) VALUES(?,?,?)",
                 (ts, score, applicable_count))
        c.executemany(
            "INSERT INTO result(ts, check_id, status, detail) VALUES(?,?,?,?)",
            [(ts, check.id, result.status, result.detail) for check, result in results],
        )
    return ts


def score_history(limit=30):
    """Most recent scans first: [(ts, score, applicable_count), ...]."""
    with _lock, conn() as c:
        rows = c.execute(
            "SELECT ts, score, applicable_count FROM scan ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return rows


def latest_scan_ts():
    with _lock, conn() as c:
        row = c.execute("SELECT MAX(ts) FROM scan").fetchone()
    return row[0] if row else None


# Ensure tables exist as soon as the module is imported, matching Kevscope's
# store.py so any entry point is safe without an explicit init() call first.
init()
