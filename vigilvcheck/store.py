"""store.py — local SQLite for posture history.

Same discipline as Kevscope's store.py: WAL mode, owner-only file
permissions. This one's purpose is narrower — it just remembers what each
scan found, so "posture over time" has something real to show instead of
only ever displaying the latest run.

Lives under the OS's per-user data directory, not next to the installed
package: the package directory isn't guaranteed writable (a locked-down or
shared Python install), and on a system-wide install it isn't per-user
either, which would leak one account's hardening gaps to every other local
account on the box. The permission narrowing also happens at file-creation
time, not as a chmod afterward — an sqlite3.connect() that creates the file
first leaves a brief window at the OS-default (often world-readable) mode
before a follow-up chmod call closes it.
"""
import os
import platform
import sqlite3
import threading
import time


def _data_dir():
    if platform.system() == "Darwin":
        return os.path.join(os.path.expanduser("~/Library/Application Support"), "VigilvCheck")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "vigilvcheck")


DATA_DIR = _data_dir()
DB_PATH = os.path.join(DATA_DIR, "vigilvcheck.db")
_lock = threading.Lock()


def _ensure_private_path(path, mode):
    """Create path (file or dir) with `mode` from the moment it exists,
    rather than creating it at the OS default and narrowing permissions
    afterward — closes the window where another local account could open
    it before the chmod call runs."""
    if os.path.isdir(path) or path.endswith(os.sep):
        os.makedirs(path, mode=mode, exist_ok=True)
        try:
            os.chmod(path, mode)   # makedirs's mode is filtered by umask; enforce it explicitly
        except OSError:
            pass
    elif not os.path.exists(path):
        fd = os.open(path, os.O_CREAT | os.O_WRONLY, mode)
        os.close(fd)
    else:
        try:
            os.chmod(path, mode)
        except OSError:
            pass


def conn():
    c = sqlite3.connect(DB_PATH, timeout=20)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init():
    _ensure_private_path(DATA_DIR + os.sep, 0o700)
    # This DB holds a record of exactly which hardening basics this machine
    # fails and why — not something to leave world-readable, and not
    # something any other local account should be able to open even briefly.
    _ensure_private_path(DB_PATH, 0o600)
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
