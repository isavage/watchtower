"""SQLite persistence: metric rows, sessions, and downsampled queries."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterable, Iterator

from .config import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    cpu_pct     REAL,
    cpu_count   INTEGER,
    load1       REAL,
    load5       REAL,
    load15      REAL,
    mem_total   REAL,
    mem_used    REAL,
    mem_pct     REAL,
    swap_total  REAL,
    swap_used   REAL,
    disk_total  REAL,
    disk_used   REAL,
    disk_pct    REAL,
    disk_read   REAL,
    disk_write  REAL,
    net_recv    REAL,
    net_sent    REAL,
    uptime      REAL,
    proc_count  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics (ts);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user        TEXT NOT NULL,
    created     REAL NOT NULL,
    last_seen   REAL NOT NULL,
    expires     REAL NOT NULL
);
"""

_COLUMNS = [
    "ts", "cpu_pct", "cpu_count", "load1", "load5", "load15",
    "mem_total", "mem_used", "mem_pct", "swap_total", "swap_used",
    "disk_total", "disk_used", "disk_pct", "disk_read", "disk_write",
    "net_recv", "net_sent", "uptime", "proc_count",
]


def _ensure_dir() -> None:
    d = os.path.dirname(os.path.abspath(config.db_path))
    os.makedirs(d, exist_ok=True)


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    _ensure_dir()
    conn = sqlite3.connect(config.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)


def insert_metrics(rows: Iterable[dict]) -> None:
    rows = list(rows)
    if not rows:
        return
    placeholders = ", ".join("?" for _ in _COLUMNS)
    cols = ", ".join(_COLUMNS)
    data = [tuple(r.get(c) for c in _COLUMNS) for r in rows]
    with get_conn() as conn:
        conn.executemany(f"INSERT INTO metrics ({cols}) VALUES ({placeholders})", data)


def latest() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM metrics ORDER BY ts DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def query_series(start: float, end: float, points: int = 180) -> list[dict]:
    """Average metric rows into ~`points` time buckets between start and end."""
    span = max(end - start, 1e-6)
    step = max(span / max(points, 1), 1e-6)
    bucket = "CAST(ts / ? AS INTEGER) * ?"
    exprs = ", ".join(f"AVG({c}) AS {c}" for c in _COLUMNS if c not in ("ts", "cpu_count"))
    # GROUP BY must repeat the bucket expression: SQLite resolves bare names in
    # GROUP BY against input columns (the raw ts), not the output alias.
    sql = (
        f"SELECT {bucket} AS ts, {exprs}, MAX(cpu_count) AS cpu_count "
        f"FROM metrics WHERE ts >= ? AND ts <= ? "
        f"GROUP BY CAST(ts / ? AS INTEGER) ORDER BY ts"
    )
    with get_conn() as conn:
        rows = conn.execute(sql, (step, step, start, end, step)).fetchall()
    return [dict(r) for r in rows]


def prune(older_than_ts: float) -> int:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM metrics WHERE ts < ?", (older_than_ts,))
    return cur.rowcount
