"""Background ingester for nginx per-site web stats.

Mirrors the sampler's split: in Docker the app has no host access, so the
log *delta* is fetched from the host-proxy sidecar (``GET /api/webstats``);
locally (no ``WT_HOST_PROXY_URL``) the same collector runs in-process against
``WT_NGINX_LOG_DIR``. Either way the result is a set of per-site aggregates
for the lines appended since the previous poll, which we stamp with the poll
time and persist via :mod:`app.store`.

Why a separate loop from the 2s metric sampler:
* Parsing logs is heavier and only meaningful per-minute, so it runs on its
  own ``WT_WEBSTATS_INTERVAL`` (default 60s).
* The host-proxy delta is *consumed* on read — exactly one poller may call
  ``/api/webstats``. This module is that single poller.

The endpoint degrades cleanly: when the proxy reports ``available: false``
(no log dir / no flag / not configured) we record nothing and the Websites
page shows an explanatory empty state rather than erroring.
"""
from __future__ import annotations

import asyncio
import logging
import time

from . import hostproxy_client, store
from .config import config

log = logging.getLogger("watchtower.webstats")

# Track the last successful window so the UI can say "collecting since …" and
# surface a stalled ingester without a separate status endpoint.
_last_ok: float | None = None
_last_error: str | None = None


def status() -> dict:
    """Ingest-loop health for the Websites page (how fresh the data is)."""
    return {"last_ok": _last_ok, "last_error": _last_error}


async def run_webstats_ingester(stop: asyncio.Event) -> None:
    """Poll the host-proxy (or local collector) and persist each window."""
    global _last_ok, _last_error

    # Local-dev fallback: run the collector in-process when there is no
    # sidecar. It is stateful, so keep one instance across polls.
    tracker = None
    if not hostproxy_client.enabled():
        try:
            from collectors import webstats as webstats_mod

            tracker = webstats_mod.WebstatsTracker()
        except Exception:  # pragma: no cover - defensive
            log.exception("webstats local collector init failed")

    log.info("webstats ingester started (interval=%ss, source=%s)",
             config.webstats_interval, "host-proxy" if hostproxy_client.enabled() else "local")

    while not stop.is_set():
        try:
            await _ingest_once(tracker)
        except Exception:
            log.exception("webstats ingest error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=config.webstats_interval)
        except asyncio.TimeoutError:
            pass


async def _ingest_once(tracker) -> None:
    global _last_ok, _last_error
    # Do the (blocking) read/parse off the event loop so a big log window
    # never stalls the metric sampler or request handling.
    delta = await asyncio.get_running_loop().run_in_executor(None, _fetch_delta, tracker)
    now = time.time()

    if delta is None:
        _last_error = "host-proxy unavailable or endpoint disabled (WT_ALLOW_WEBSTATS)"
        return
    if not delta.get("available"):
        # Not an outage — the deployment simply has no nginx logs configured.
        _last_error = delta.get("error") or "webstats unavailable"
        _last_ok = now
        return

    sites = delta.get("sites") or []
    written = store.insert_webstats(now, sites)
    _last_ok = now
    _last_error = None
    if written:
        log.info("webstats: stored %d site rows (%d requests, %d malformed)",
                 written, sum(s.get("requests", 0) for s in sites), delta.get("malformed", 0))


def _fetch_delta(tracker) -> dict | None:
    if hostproxy_client.enabled():
        data = hostproxy_client.get("/api/webstats", timeout=20.0)
        return data if isinstance(data, dict) else None
    if tracker is None:
        return {"available": False, "error": "local webstats collector unavailable"}
    return tracker.poll()
