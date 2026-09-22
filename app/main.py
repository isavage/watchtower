"""FastAPI application: API + static SPA + background sampler."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import store
from . import docker as docker_mod
from .api import auth_routes, metrics_routes
from .config import config
from . import hostproxy_client
from .sampler import run_sampler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("watchtower")

WEB_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    stop = asyncio.Event()
    task = asyncio.create_task(run_sampler(stop))
    log.info(
        "watchtower started (interval=%ss, host_source=%s, db=%s)",
        config.sample_interval,
        config.host_proxy_url or "local /proc",
        config.db_path,
    )
    try:
        yield
    finally:
        stop.set()
        await task


app = FastAPI(title="Watchtower", lifespan=lifespan)
app.include_router(auth_routes.router)
app.include_router(metrics_routes.router)


@app.get("/api/health")
def health() -> dict:
    """Liveness for the app *and* its sidecars.

    When host-proxy or docker-proxy is down, the dashboard would otherwise
    keep serving 200s full of empty/stale host stats. Reporting them here
    lets the compose healthcheck (and any monitor) go red instead. Login
    keeps working either way — only the data planes are gated.
    """
    checks = {
        "host_proxy": hostproxy_client.healthy(),
        # In local dev the docker socket may simply not exist and the Docker
        # pages degrade gracefully; only a down docker-proxy sidecar (tcp) is
        # a real outage worth marking the container unhealthy for.
        "docker": docker_mod.healthy() if config.docker_socket.startswith("tcp://") else True,
    }
    ok = all(checks.values())
    body = {"ok": ok, "checks": checks}
    return JSONResponse(body, status_code=200 if ok else 503)


# ---- static SPA (built React app) ----
if os.path.isdir(WEB_DIST):
    assets = os.path.join(WEB_DIST, "assets")
    if os.path.isdir(assets):
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = os.path.normpath(os.path.join(WEB_DIST, full_path))
        if full_path and candidate.startswith(WEB_DIST) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(WEB_DIST, "index.html"))
else:
    @app.get("/", include_in_schema=False)
    def no_ui() -> JSONResponse:
        return JSONResponse(
            {"detail": "UI not built yet — run `npm run build` in web/ or use the API directly."},
            status_code=404,
        )
