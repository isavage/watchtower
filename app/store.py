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

-- Per-site nginx access-log aggregates, one row per (site, ingest window).
-- Rows are *deltas* produced by collectors/webstats.py in the host-proxy, so
-- summing them over a range gives exact request counts for that range.
-- `visitors` is the unique-client-IP count *within the window*; summing it
-- across windows over-counts repeat visitors, which the UI labels as
-- approximate. Raw IPs, paths-as-logs and user agents are never stored.
CREATE TABLE IF NOT EXISTS webstats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    site        TEXT NOT NULL,
    requests    INTEGER NOT NULL,
    s2xx        INTEGER NOT NULL DEFAULT 0,
    s3xx        INTEGER NOT NULL DEFAULT 0,
    s4xx        INTEGER NOT NULL DEFAULT 0,
    s5xx        INTEGER NOT NULL DEFAULT 0,
    bytes       INTEGER NOT NULL DEFAULT 0,
    visitors    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_webstats_ts ON webstats (ts);
CREATE INDEX IF NOT EXISTS idx_webstats_site_ts ON webstats (site, ts);

-- Top paths per site per window (already ranked + capped at the source).
CREATE TABLE IF NOT EXISTS webstats_paths (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    site        TEXT NOT NULL,
    path        TEXT NOT NULL,
    count       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_webstats_paths_ts ON webstats_paths (ts);
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
    """Drop metric rows and webstats rows past the retention window."""
    with get_conn() as conn:
        n_metrics = conn.execute("DELETE FROM metrics WHERE ts < ?", (older_than_ts,)).rowcount
        n_web = conn.execute("DELETE FROM webstats WHERE ts < ?", (older_than_ts,)).rowcount
        conn.execute("DELETE FROM webstats_paths WHERE ts < ?", (older_than_ts,))
    return n_metrics + n_web


# ---- webstats (nginx per-site access-log aggregates) ----

_WS_COLUMNS = ["ts", "site", "requests", "s2xx", "s3xx", "s4xx", "s5xx", "bytes", "visitors"]


def insert_webstats(window_ts: float, sites: Iterable[dict]) -> int:
    """Persist one ingest window's per-site deltas. Returns rows written.

    ``window_ts`` stamps every row so a range query sums whole windows. Top
    paths are stored separately (already ranked + capped by the collector).
    """
    sites = [s for s in sites if s.get("requests")]
    if not sites:
        return 0
    main_rows = [
        (window_ts, s["site"], int(s.get("requests", 0)), int(s.get("s2xx", 0)),
         int(s.get("s3xx", 0)), int(s.get("s4xx", 0)), int(s.get("s5xx", 0)),
         int(s.get("bytes", 0)), int(s.get("visitors", 0)))
        for s in sites
    ]
    path_rows = [
        (window_ts, s["site"], p["path"], int(p["count"]))
        for s in sites
        for p in (s.get("top_paths") or [])
    ]
    placeholders = ", ".join("?" for _ in _WS_COLUMNS)
    cols = ", ".join(_WS_COLUMNS)
    with get_conn() as conn:
        conn.executemany(f"INSERT INTO webstats ({cols}) VALUES ({placeholders})", main_rows)
        if path_rows:
            conn.executemany(
                "INSERT INTO webstats_paths (ts, site, path, count) VALUES (?, ?, ?, ?)",
                path_rows,
            )
    return len(main_rows)


def webstats_sites(start: float, end: float) -> list[dict]:
    """Per-site totals over [start, end]: summed requests/bytes + visitor sum.

    ``visitors`` is summed across windows, so it over-counts a client seen in
    more than one window — an upper bound, labelled approximate in the UI.
    """
    sql = (
        "SELECT site, SUM(requests) AS requests, SUM(s2xx) AS s2xx, SUM(s3xx) AS s3xx, "
        "SUM(s4xx) AS s4xx, SUM(s5xx) AS s5xx, SUM(bytes) AS bytes, SUM(visitors) AS visitors, "
        "MAX(ts) AS last_seen "
        "FROM webstats WHERE ts >= ? AND ts <= ? "
        "GROUP BY site ORDER BY requests DESC"
    )
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, (start, end)).fetchall()]


def webstats_series(start: float, end: float, points: int = 120) -> list[dict]:
    """Total requests/bytes bucketed across all sites for the range chart."""
    span = max(end - start, 1e-6)
    step = max(span / max(points, 1), 1e-6)
    bucket = "CAST(ts / ? AS INTEGER) * ?"
    sql = (
        f"SELECT {bucket} AS ts, SUM(requests) AS requests, SUM(bytes) AS bytes, "
        f"SUM(s4xx + s5xx) AS errors "
        f"FROM webstats WHERE ts >= ? AND ts <= ? "
        f"GROUP BY CAST(ts / ? AS INTEGER) ORDER BY ts"
    )
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, (step, step, start, end, step)).fetchall()]


def webstats_site_series(site: str, start: float, end: float, points: int = 120) -> list[dict]:
    """Requests/bytes/errors bucketed for one site over the range."""
    span = max(end - start, 1e-6)
    step = max(span / max(points, 1), 1e-6)
    bucket = "CAST(ts / ? AS INTEGER) * ?"
    sql = (
        f"SELECT {bucket} AS ts, SUM(requests) AS requests, SUM(bytes) AS bytes, "
        f"SUM(s4xx + s5xx) AS errors "
        f"FROM webstats WHERE site = ? AND ts >= ? AND ts <= ? "
        f"GROUP BY CAST(ts / ? AS INTEGER) ORDER BY ts"
    )
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, (step, step, site, start, end, step)).fetchall()]


def webstats_top_paths(site: str, start: float, end: float, limit: int = 10) -> list[dict]:
    """Most-requested paths for one site over the range (paths summed)."""
    sql = (
        "SELECT path, SUM(count) AS count FROM webstats_paths "
        "WHERE site = ? AND ts >= ? AND ts <= ? "
        "GROUP BY path ORDER BY count DESC LIMIT ?"
    )
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, (site, start, end, limit)).fetchall()]
