"""watchtower-host-proxy server: read-only host facts over HTTP.

The container that owns *all* host access in the stack (`pid: host`, the
`/proc` `/sys` `/etc/...` mounts). The UI app talks to it exactly like it
talks to docker-socket-proxy — one narrow, allow-listed, token-gated API.

Hard rules enforced here:

* GET only; anything else is 405. There is no write path at all.
* Every data endpoint requires `Authorization: Bearer $WT_HOST_PROXY_TOKEN`
  (constant-time compare). An unset token disables them (503, fail closed).
* Each endpoint answers only when its own `WT_ALLOW_*` flag is on (403
  otherwise), so a deployment can deny the Security page's file reads while
  keeping metrics, or vice versa.
* There is no request-borne file path anywhere: the endpoint set is fixed
  and each handler reads exactly the files its collector parses, so path
  traversal is not a reachable surface.

Collection logic lives in the shared top-level `collectors/` package (single
source of truth, also used by the app's local-dev fallback); this service adds
transport + policy, nothing else.
"""
from __future__ import annotations

import hmac
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from collectors import collector, details as details_mod, security
from collectors.hostconfig import host_config

from .config import proxy_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("hostproxy")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info(
        "host-proxy up (host_proc=%s, allow=%s, token=%s)",
        host_config.proc_path,
        proxy_config.allow_map(),
        "set" if proxy_config.token else "MISSING — endpoints disabled",
    )
    yield


app = FastAPI(
    title="watchtower-host-proxy",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# endpoint key -> its allow flag, kept in sync with config.allow_map()
_ENDPOINTS = ("metrics", "details", "security")


def _denied(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status_code)


@app.middleware("http")
async def policy(request: Request, call_next):
    """Method gate + bearer auth for every /api/* data route."""
    path = request.url.path

    # /health stays open (no host data) so container healthchecks need no token.
    if path == "/api/health":
        return await call_next(request)

    if request.method != "GET":
        return _denied(405, "host-proxy serves GET only")

    if not path.startswith("/api/"):
        return _denied(404, "Not found")

    if not proxy_config.token:
        return _denied(503, "host-proxy disabled: WT_HOST_PROXY_TOKEN is not set")
    supplied = request.headers.get("authorization", "")
    prefix = "Bearer "
    if not supplied.startswith(prefix):
        return _denied(401, "Missing bearer token")
    if not hmac.compare_digest(supplied[len(prefix):], proxy_config.token):
        return _denied(401, "Invalid token")

    return await call_next(request)


@app.middleware("http")
async def access_log(request: Request, call_next):
    """Log every served request: method, path(+query), status, latency.

    Registered after `policy` so it wraps it and records the *final* status,
    including 401/403/405 denials — the audit trail for a UI session that was
    abused with a valid token. Bodies and the Authorization header are never
    logged (the bearer is a static credential; syslog would keep it forever).
    """
    start = time.perf_counter()
    response = await call_next(request)
    log.info(
        "%s %s%s -> %s (%.1fms)",
        request.method,
        request.url.path,
        f"?{request.url.query}" if request.url.query else "",
        response.status_code,
        (time.perf_counter() - start) * 1000,
    )
    return response


@app.get("/api/health")
def health() -> dict:
    """Liveness + policy snapshot (no host data; token-free by design)."""
    return {
        "ok": True,
        "read_only": True,
        "host_proc": host_config.proc_path,
        "token_configured": bool(proxy_config.token),
        "allow": proxy_config.allow_map(),
        "ts": time.time(),
    }


def _guard(key: str):
    if not getattr(proxy_config, f"allow_{key}"):
        return _denied(403, f"endpoint disabled: set WT_ALLOW_{key.upper()}=1 to allow")
    return None


# One stateful Collector for the process: it keeps previous disk/net counters
# so the per-second rates are real. A fresh instance per request would always
# report zero rates (the client docstring relies on this being stateful).
_collector = collector.Collector()


@app.get("/api/sample")
def sample():
    """One collector sample — the dashboard's metric row."""
    denied = _guard("metrics")
    if denied:
        return denied
    return _collector.sample()


@app.get("/api/details")
def details(limit: int = Query(15, ge=5, le=50)):
    """Live drill-down: per-core CPU, memory, partitions, disk I/O, NICs, processes."""
    denied = _guard("details")
    if denied:
        return denied
    return details_mod.details(limit=limit)


@app.get("/api/security")
def security_snapshot():
    """Firewall / sshd / listener / auth-log facts from the mounted config files."""
    denied = _guard("security")
    if denied:
        return denied
    return security.snapshot()
