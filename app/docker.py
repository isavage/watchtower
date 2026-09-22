"""Docker container listing + live CPU/mem/net/blkio via the Engine API.

Uses a plain HTTP-over-unix-socket client so no extra dependency is required.
If the socket is not mounted the endpoint degrades gracefully to
``{"available": False}``.
"""
from __future__ import annotations

import http.client
import json
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psutil

from .config import config

log = logging.getLogger("watchtower.docker")


class _UnixConn(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float = 5.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self._path = path

    def connect(self) -> None:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self._path)
        self.sock = s


def _target() -> tuple[str, int | None]:
    """WT_DOCKER_SOCKET as (unix path, None) or (tcp host, tcp port)."""
    value = config.docker_socket
    if value.startswith("tcp://"):
        host, _, port = value[len("tcp://"):].rpartition(":")
        return host, int(port or 2375)
    return value, None


def _conn(timeout: float) -> http.client.HTTPConnection:
    target, port = _target()
    if port is not None:
        return http.client.HTTPConnection(target, port=port, timeout=timeout)
    return _UnixConn(target, timeout=timeout)


def _get(path: str, timeout: float = 5.0) -> object | None:
    try:
        conn = _conn(timeout)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        if resp.status >= 400:
            log.warning("docker API %s -> %s", path, resp.status)
            return None
        return json.loads(body)
    except (FileNotFoundError, PermissionError, ConnectionError, socket.timeout, OSError):
        return None
    except json.JSONDecodeError:
        return None


def _socket_present() -> bool:
    target, port = _target()
    try:
        if port is not None:
            with socket.create_connection((target, port), timeout=2):
                return True
        s = socket.socket(socket.AF_UNIX)
        try:
            return s.connect_ex(target) == 0
        finally:
            s.close()
    except OSError:
        return False


def healthy() -> bool:
    """Reachable Docker API (socket or docker-proxy)? Used by /api/health."""
    return _socket_present()


def _cpu_percent(stats: dict) -> float:
    cur = stats.get("cpu_stats") or {}
    prev = stats.get("precpu_stats") or {}
    delta_sys = cur.get("system_cpu_usage", 0) - prev.get("system_cpu_usage", 0)
    delta_total = (cur.get("cpu_usage") or {}).get("total_usage", 0) - (
        (prev.get("cpu_usage") or {}).get("total_usage", 0)
    )
    if delta_sys <= 0 or delta_total <= 0:
        return 0.0
    cores = cur.get("online_cpus") or 1  # cgroup v2; v1 falls back to 1
    return min(delta_total / delta_sys * cores * 100.0, 100.0 * cores)


def _mem_stats(stats: dict) -> tuple[float | None, float | None, float | None]:
    mem = stats.get("memory_stats") or {}
    usage = mem.get("usage")
    limit = mem.get("limit")
    cached = (mem.get("stats") or {}).get("inactive_file") or 0
    if usage is not None:
        usage = max(usage - cached, 0)
    if usage is not None and limit:
        return float(usage), float(limit), min(usage / limit * 100.0, 100.0)
    return (float(usage) if usage is not None else None), (float(limit) if limit else None), None


def _net_bytes(stats: dict) -> tuple[float, float]:
    rx = tx = 0
    for iface in (stats.get("networks") or {}).values():
        rx += iface.get("rx_bytes", 0)
        tx += iface.get("tx_bytes", 0)
    return float(rx), float(tx)


def _blkio_bytes(stats: dict) -> float:
    total = 0
    for dev in (stats.get("blkio_stats") or {}).get("io_service_bytes_recursive") or []:
        total += dev.get("value", 0)
    return float(total)


def _age_seconds(created: str | int | float | None) -> float | None:
    if created is None or created == "":
        return None
    try:
        if isinstance(created, (int, float)):
            # Docker Engine API returns Created as a unix timestamp (seconds).
            dt = datetime.fromtimestamp(created, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        return max((datetime.now(timezone.utc) - dt).total_seconds(), 0.0)
    except (ValueError, OSError, OverflowError):
        return None


def _dedupe_ports(ports: list) -> list:
    """Collapse the IPv4/IPv6 twins the Engine API reports per bind address.

    /containers/json lists a published port once for 0.0.0.0 and once for ::,
    which rendered as the same badge twice in the UI. The IP field is dropped
    entirely (we never show it), so dedupe on what we actually display.
    """
    seen: set = set()
    out: list = []
    for p in ports:
        if not isinstance(p, dict):
            continue
        key = (p.get("PrivatePort"), p.get("PublicPort"), p.get("Type"))
        if key in seen:
            continue
        seen.add(key)
        out.append({k: v for k, v in p.items() if k != "IP"})
    return out


def images() -> dict:
    if not _socket_present():
        return {"available": False, "images": []}
    items = _get("/images/json")
    if not isinstance(items, list):
        return {"available": False, "images": []}
    return {"available": True, "images": [{"id": str(i.get("Id", ""))[-12:], "tags": i.get("RepoTags") or [], "size": float(i.get("Size") or 0), "created": i.get("Created")} for i in items]}


def networks() -> dict:
    if not _socket_present():
        return {"available": False, "networks": []}
    items = _get("/networks")
    if not isinstance(items, list):
        return {"available": False, "networks": []}
    rows = []
    for item in items:
        ipam = item.get("IPAM") or {}
        rows.append({"id": str(item.get("Id", ""))[:12], "name": item.get("Name", ""), "driver": item.get("Driver", ""), "scope": item.get("Scope", ""), "internal": bool(item.get("Internal")), "subnets": [c.get("Subnet") for c in (ipam.get("Config") or []) if c.get("Subnet")], "gateways": [c.get("Gateway") for c in (ipam.get("Config") or []) if c.get("Gateway")], "containers": len(item.get("Containers") or {})})
    return {"available": True, "networks": rows}


def containers() -> dict:
    if not _socket_present():
        return {"available": False, "containers": []}

    items = _get("/containers/json?all=false")
    if items is None:
        return {"available": False, "containers": []}

    mem_total = psutil.virtual_memory().total

    def _build_row(it: dict) -> dict:
        cid = it.get("Id", "")
        row: dict = {
            "id": cid[:12],
            "name": (it.get("Names") or [cid[:12]])[0].lstrip("/"),
            "image": it.get("Image", "?"),
            "ports": _dedupe_ports(it.get("Ports") or []),
            "state": it.get("State", "unknown"),
            "status": it.get("Status", ""),
            "age": _age_seconds(it.get("Created")),
            "cpu_pct": None,
            "mem_usage": None,
            "mem_limit": None,
            "mem_pct": None,
            "net_rx": None,
            "net_tx": None,
            "blkio": None,
            "pids": None,
        }
        # Each stats call blocks ~1s inside the daemon (one sampling interval),
        # so fetch them concurrently instead of serially.
        stats = _get(f"/containers/{cid}/stats?stream=false", timeout=8.0)
        if isinstance(stats, dict):
            row["cpu_pct"] = round(_cpu_percent(stats), 2)
            usage, limit, pct = _mem_stats(stats)
            row["mem_usage"] = usage
            row["mem_limit"] = limit or mem_total
            row["mem_pct"] = round(pct, 2) if pct is not None else None
            rx, tx = _net_bytes(stats)
            row["net_rx"] = rx
            row["net_tx"] = tx
            row["blkio"] = _blkio_bytes(stats)
            pid_entry = (stats.get("pstats") or {}).get("pid_stats") or {}
            if pid_entry:
                row["pids"] = next(iter(pid_entry.values()), {}).get("current_pids")
        return row

    workers = min(8, max(2, len(items)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        out = list(pool.map(_build_row, items))

    out.sort(key=lambda r: (r.get("cpu_pct") or 0), reverse=True)
    return {
        "available": True,
        "count": len(out),
        "cpu_total": round(sum(r.get("cpu_pct") or 0 for r in out), 2),
        "memory": {"total": sum(r.get("mem_usage") or 0 for r in out)},
        "containers": out,
    }
