from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import auth, docker as docker_mod, hostproxy_client, store
from .. import webstats as webstats_mod
from collectors import details, security

router = APIRouter(prefix="/api", tags=["metrics"], dependencies=[Depends(auth.current_user)])

# range key -> (seconds, target chart points)
RANGES: dict[str, tuple[float, int]] = {
    "5m": (5 * 60, 100),
    "15m": (15 * 60, 120),
    "1h": (3600, 150),
    "6h": (6 * 3600, 180),
    "24h": (24 * 3600, 200),
    "7d": (7 * 24 * 3600, 240),
}


def _clean(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {k: v for k, v in row.items()}


@router.get("/summary")
def summary() -> dict:
    """Latest live values for the header/stat cards."""
    return {"latest": _clean(store.latest())}


@router.get("/series")
def series(
    range: str = Query("1h", pattern="^(5m|15m|1h|6h|24h|7d)$"),
    since: float | None = Query(None, description="Override: epoch seconds"),
    until: float | None = Query(None, description="Override: epoch seconds"),
) -> dict:
    seconds, points = RANGES[range]
    end = until if until is not None else time.time()
    start = since if since is not None else end - seconds
    data = store.query_series(start, end, points)
    return {"range": range, "start": start, "end": end, "points": data}


@router.get("/details")
def details_endpoint(
    limit: int = Query(15, ge=5, le=50, description="Top-N processes per sort"),
) -> dict:
    """Live per-core / per-process / per-disk / per-NIC detail."""
    if hostproxy_client.enabled():
        data = hostproxy_client.get("/api/details", params={"limit": limit})
        if not isinstance(data, dict):
            raise HTTPException(status_code=503, detail="host-proxy unavailable (or endpoint disabled)")
        return data
    return details.details(limit=limit)


@router.get("/security")
def security_endpoint() -> dict:
    """Read-only firewall, SSH, and listener facts from the host."""
    if hostproxy_client.enabled():
        data = hostproxy_client.get("/api/security")
        if not isinstance(data, dict):
            raise HTTPException(status_code=503, detail="host-proxy unavailable (or WT_ALLOW_SECURITY=0)")
        return data
    return security.snapshot()


@router.get("/webstats")
def webstats_endpoint(
    range: str = Query("24h", pattern="^(5m|15m|1h|6h|24h|7d)$"),
    site: str | None = Query(None, max_length=255, description="Drill into one site"),
) -> dict:
    """Per-site nginx stats from the SQLite store, filled by the ingester.

    Reads only our own DB — the log files stay behind the host-proxy, and
    the stored rows are derived aggregates (no IPs, no raw lines).
    """
    seconds, points = RANGES[range]
    end = time.time()
    start = end - seconds
    out = {
        "range": range,
        "start": start,
        "end": end,
        "sites": store.webstats_sites(start, end),
        "series": store.webstats_series(start, end, points),
        "status": webstats_mod.status(),
    }
    if site:
        out["site"] = site
        out["site_series"] = store.webstats_site_series(site, start, end, points)
        out["top_paths"] = store.webstats_top_paths(site, start, end)
    return out


@router.get("/docker/images")
def docker_images_endpoint() -> dict:
    return docker_mod.images()


@router.get("/docker/networks")
def docker_networks_endpoint() -> dict:
    return docker_mod.networks()


@router.get("/docker/volumes")
def docker_volumes_endpoint() -> dict:
    return docker_mod.volumes()


@router.get("/docker")
def docker_endpoint() -> dict:
    """Running containers with live CPU/mem/net/blkio, or available=False."""
    return docker_mod.containers()
