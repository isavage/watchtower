"""Nginx access-log stats for the Websites page.

Runs inside the host-proxy (the only container with host visibility) and
returns *deltas*: each ``poll()`` parses only the bytes appended to the log
files since the previous call, so the app can ingest per-window aggregates
into SQLite without ever shipping raw log lines over the wire.

Design notes / invariants:

* Stateful like ``collector.Collector``: byte offsets per file must persist
  between polls (hostproxy keeps one module-level tracker). A fresh instance
  would re-read the tail on every call and double-count.
* Rotation-safe: we track ``(inode, offset)``; a replaced file (logrotate) or
  a truncated one resets to a capped tail read instead of reading garbage.
* First sight of a file reads at most ``WT_WEBSTATS_TAIL_MB`` (default 8 MB)
  of history, marked ``backfilled`` — a 2 GB log must never be parsed whole.
* Never raises: a missing/unreadable directory answers
  ``{"available": false, "error": ...}`` like the other collectors.
* Only the *derived* aggregates leave the process (counts, byte sums, top
  paths). Client IPs are reduced to a per-window unique count; raw IPs,
  user agents and full request lines never appear in the payload.

Log layout: one file per site under ``WT_NGINX_LOG_DIR`` (host path, mapped
through ``WT_HOST_ROOT`` like every other host read). The site name comes
from the filename (``example.com.access.log`` -> ``example.com``);
error/debug logs are skipped since they are not combined format.
"""
from __future__ import annotations

import os
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from .hostconfig import host_config

# Nginx combined format:
# $remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent
#                  "$http_referer" "$http_user_agent"
_LOG_RE = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<req>[^"]*)"'
    r" (?P<status>\d{3}) (?P<bytes>\d+|-)"
)

# example.com.access.log / example.com.log / example.com-access.log.1 -> example.com
_NAME_RE = re.compile(r"[-.]?(access|error)?\.log(\.\d+)?$", re.I)

# Files that are obviously not per-site access logs.
_SKIP_RE = re.compile(r"(error|debug|audit)\.log", re.I)

_MAX_BYTES_PER_POLL = 64 * 1024 * 1024  # parse at most 64 MB per poll, all files
_TOP_PATHS = 8


def _env_bytes(name: str, default_mb: int) -> int:
    try:
        mb = int(os.environ.get(name, "").strip() or default_mb)
    except ValueError:
        mb = default_mb
    return max(mb, 1) * 1024 * 1024


def _log_dir() -> tuple[Path | None, str | None]:
    """The configured nginx log dir, mapped under WT_HOST_ROOT like other host reads."""
    raw = os.environ.get("WT_NGINX_LOG_DIR", "").strip()
    if not raw:
        return None, "WT_NGINX_LOG_DIR is not set on the host-proxy"
    path = Path(host_config.host_root) / raw.lstrip("/") if host_config.host_root else Path(raw)
    if not path.is_dir():
        return None, f"log directory not found: {raw} (mounted at {path})"
    return path, None


def site_name(fname: str) -> str:
    name = _NAME_RE.sub("", fname)
    return name or fname


def _parse_time(local: str) -> float | None:
    try:
        return datetime.strptime(local, "%d/%b/%Y:%H:%M:%S %z").timestamp()
    except ValueError:
        return None


class SiteAgg:
    __slots__ = ("requests", "classes", "bytes", "ips", "paths", "first_ts", "last_ts")

    def __init__(self) -> None:
        self.requests = 0
        self.classes = [0, 0, 0, 0, 0]  # counts by status/100 (1xx..5xx)
        self.bytes = 0
        self.ips: set[str] = set()
        self.paths: Counter[str] = Counter()
        self.first_ts: float | None = None
        self.last_ts: float | None = None

    def add(self, ts: float | None, ip: str, status: int, sent: int, path: str) -> None:
        self.requests += 1
        cls = status // 100
        if 1 <= cls <= 5:
            self.classes[cls - 1] += 1
        self.bytes += sent
        self.ips.add(ip)
        if path and path != "-":
            self.paths[path.split("?", 1)[0]] += 1
        if ts is not None:
            self.first_ts = ts if self.first_ts is None else min(self.first_ts, ts)
            self.last_ts = ts if self.last_ts is None else max(self.last_ts, ts)

    def payload(self) -> dict:
        return {
            "requests": self.requests,
            "s2xx": self.classes[1],
            "s3xx": self.classes[2],
            "s4xx": self.classes[3],
            "s5xx": self.classes[4],
            "bytes": self.bytes,
            "visitors": len(self.ips),
            "top_paths": [{"path": p, "count": c} for p, c in self.paths.most_common(_TOP_PATHS)],
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
        }


class WebstatsTracker:
    """Delta reader over per-site nginx access logs (stateful across polls)."""

    def __init__(self) -> None:
        # file path -> {"ino": int, "off": int}
        self._states: dict[str, dict[str, int]] = {}
        self._last_poll: float | None = None

    def poll(self) -> dict:
        now = time.time()
        window_start = self._last_poll
        self._last_poll = now

        directory, dir_error = _log_dir()
        if directory is None:
            return {"ts": now, "available": False, "error": dir_error,
                    "sites": [], "files": [], "parsed": 0, "malformed": 0}

        tail_cap = _env_bytes("WT_WEBSTATS_TAIL_MB", 8)
        sites: dict[str, SiteAgg] = {}
        files: list[dict] = []
        malformed = 0
        parsed = 0
        budget = _MAX_BYTES_PER_POLL

        try:
            entries = sorted(directory.iterdir())
        except OSError as exc:
            return {"ts": now, "available": False, "error": f"cannot list {directory}: {exc}",
                    "sites": [], "files": [], "parsed": 0, "malformed": 0}

        seen: set[str] = set()
        for entry in entries:
            try:
                if not entry.is_file() or not entry.name.endswith(".log"):
                    continue
                if _SKIP_RE.search(entry.name):
                    continue
                st = entry.stat()
            except OSError:
                continue
            key = str(entry)
            seen.add(key)
            state = self._states.get(key)
            backfilled = False
            if state is None or state["ino"] != st.st_ino or st.st_size < state["off"]:
                # first sight, rotated (new inode) or truncated: start from a
                # capped tail so a huge log never gets parsed whole.
                off = max(0, st.st_size - tail_cap)
                state = {"ino": st.st_ino, "off": off}
                self._states[key] = state
                backfilled = st.st_size > off

            to_read = min(st.st_size - state["off"], budget)
            if to_read > 0:
                n_ok, n_bad, consumed = _read_lines(entry, state["off"], to_read, site_name(entry.name), sites)
                state["off"] += consumed
                budget -= consumed
                parsed += n_ok
                malformed += n_bad

            files.append({
                "file": entry.name,
                "site": site_name(entry.name),
                "size": st.st_size,
                "offset": state["off"],
                "backfilled": backfilled,
            })

        # Forget files that disappeared (rotation cleanup).
        for gone in [k for k in self._states if k not in seen]:
            del self._states[gone]

        return {
            "ts": now,
            "window_start": window_start,
            "available": True,
            "log_dir": os.environ.get("WT_NGINX_LOG_DIR", "").strip(),
            "sites": [{"site": name, **agg.payload()} for name, agg in sorted(sites.items()) if agg.requests],
            "files": files,
            "parsed": parsed,
            "malformed": malformed,
        }


def _read_lines(path: Path, offset: int, to_read: int, site_key: str, sites: dict[str, SiteAgg]) -> tuple[int, int, int]:
    """Parse complete lines from ``offset``; returns (parsed, malformed, bytes consumed).

    A trailing partial line (nginx may be mid-write) is NOT counted as
    consumed — the next poll re-reads it once the line is finished.
    """
    ok = bad = 0
    consumed = 0
    leftover = b""
    try:
        with open(path, "rb") as fh:
            fh.seek(offset)
            remaining = to_read
            while remaining > 0:
                chunk = fh.read(min(remaining, 1024 * 1024))
                if not chunk:
                    break
                remaining -= len(chunk)
                data = leftover + chunk
                lines = data.split(b"\n")
                if data.endswith(b"\n"):
                    leftover = b""
                    lines.pop()  # trailing empty piece after the final newline
                else:
                    leftover = lines.pop()  # partial line, keep for next chunk
                for raw in lines:
                    consumed += len(raw) + 1
                    if _add_line(raw, site_key, sites):
                        ok += 1
                    else:
                        bad += 1
    except OSError:
        return ok, bad, consumed
    return ok, bad, consumed


def _add_line(raw: bytes, site_key: str, sites: dict[str, SiteAgg]) -> bool:
    """Feed one log line into the per-site aggregates; False if unparseable."""
    line = raw.decode(errors="replace")
    match = _LOG_RE.search(line)
    if not match:
        return False
    try:
        status = int(match.group("status"))
    except ValueError:
        return False
    bytes_text = match.group("bytes")
    sent = int(bytes_text) if bytes_text.isdigit() else 0
    parts = match.group("req").split(" ")
    path = parts[1] if len(parts) >= 2 else ""
    agg = sites.get(site_key)
    if agg is None:
        agg = sites[site_key] = SiteAgg()
    agg.add(_parse_time(match.group("time")), match.group("ip"), status, sent, path)
    return True
