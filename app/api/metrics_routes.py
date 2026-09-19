from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query

from .. import auth, details, docker as docker_mod, security, store

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
    return details.details(limit=limit)


@router.get("/security")
def security_endpoint() -> dict:
    """Read-only firewall, SSH, and listener facts from the host."""
    return security.snapshot()


@router.get("/docker/images")
def docker_images_endpoint() -> dict:
    return docker_mod.images()


@router.get("/docker/networks")
def docker_networks_endpoint() -> dict:
    return docker_mod.networks()


@router.get("/docker")
def docker_endpoint() -> dict:
    """Running containers with live CPU/mem/net/blkio, or available=False."""
    return docker_mod.containers()
