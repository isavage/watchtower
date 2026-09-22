"""HTTP client for the watchtower-host-proxy sidecar.

Mirrors the docker-socket-proxy pattern: the app container holds **no** host
access (no `pid: host`, no /proc mounts) and asks a dedicated sidecar over an
internal Docker network, authenticating with a bearer token.

When ``WT_HOST_PROXY_URL`` is empty (local dev, single-process mode) callers
fall back to reading the host directly via psutil, so the same code works in
both deployments.
"""
from __future__ import annotations

import http.client
import json
import logging
from urllib.parse import urlencode, urlparse

from .config import config

log = logging.getLogger("watchtower.hostproxy")


class HostProxyError(RuntimeError):
    """The host-proxy is configured but could not serve the request."""


def enabled() -> bool:
    """True when host facts must come from the sidecar, not local /proc."""
    return bool(config.host_proxy_url)


def healthy(timeout: float = 3.0) -> bool:
    """Reachable host-proxy? Hits the token-free /api/health (point 21).

    Only meaningful when the sidecar is in use; with no WT_HOST_PROXY_URL the
    app reads /proc itself, so there is nothing to probe.
    """
    if not enabled():
        return True
    return isinstance(get("/api/health", timeout=timeout), dict)


def _conn(timeout: float) -> http.client.HTTPConnection:
    url = urlparse(config.host_proxy_url)
    if url.scheme not in ("http", ""):
        raise HostProxyError(f"unsupported scheme in WT_HOST_PROXY_URL: {url.scheme!r}")
    return http.client.HTTPConnection(url.hostname or "127.0.0.1", port=url.port or 80, timeout=timeout)


def get(path: str, params: dict | None = None, timeout: float = 8.0) -> object | None:
    """GET from the host-proxy; None on any transport or HTTP error.

    Denied endpoints (403), an unset proxy token (503) and unreachable-host
    all collapse to None so callers degrade uniformly; the reason is logged.

    ``path`` is restricted to the sidecar's fixed endpoint set — callers pass
    literals, never request-borne data — so the app can never be turned into
    an open proxy onto host-proxy.net (point 22).
    """
    if not path.startswith("/api/"):
        raise HostProxyError(f"refused non-sidecar path: {path!r}")
    if not enabled():
        return None
    if params:
        path = f"{path}?{urlencode(params)}"
    headers = {"Accept": "application/json"}
    if config.host_proxy_token:
        headers["Authorization"] = f"Bearer {config.host_proxy_token}"
    try:
        conn = _conn(timeout)
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        if resp.status >= 400:
            log.warning("host-proxy %s -> HTTP %s: %s", path, resp.status, body[:200].decode(errors="replace"))
            return None
        return json.loads(body)
    except (OSError, ValueError) as exc:
        log.warning("host-proxy %s failed: %s", path, exc)
        return None


class RemoteCollector:
    """Drop-in replacement for ``collectors.collector.Collector``.
    The proxy keeps one stateful Collector in its own process, so rate
    deltas (disk/net bytes per second) are computed host-side and this
    client just forwards rows to the sampler.
    """

    def sample(self) -> dict:
        row = get("/api/sample")
        if not isinstance(row, dict):
            raise HostProxyError("host-proxy /api/sample unavailable")
        return row
