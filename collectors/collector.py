"""Host metric collection via psutil.

In Docker we mount the host's /proc (see docker-compose.yml) and point psutil
at it via PROCFS_PATH, sharing the host PID namespace, so every reading
reflects the VPS itself. With no mount (local dev) it reports this machine.
"""
from __future__ import annotations

import os
import time

import psutil

from . import hostnet
from .hostconfig import host_config

if host_config.uses_host_proc:
    psutil.PROCFS_PATH = host_config.proc_path

# Root filesystem path: the host bind-mount when present, else our own "/".
_ROOT = host_config.host_root or "/"
if host_config.host_root and not os.path.isdir(_ROOT):
    _ROOT = "/"


def _net_totals() -> tuple[int, int] | None:
    """Host-wide (bytes_recv, bytes_sent).

    psutil only sees the container's own veth, so in Docker we sum the host's
    /proc/net/dev instead. Falls back to psutil when the mount is absent.
    """
    if hostnet.host_mode():
        dev = hostnet.net_dev()
        if dev is not None:
            return (
                sum(c["rx_bytes"] for c in dev.values()),
                sum(c["tx_bytes"] for c in dev.values()),
            )
    n = psutil.net_io_counters()
    return (n.bytes_recv, n.bytes_sent) if n else None


class Collector:
    """Stateful sampler: keeps previous counters to derive rates."""

    def __init__(self) -> None:
        self._prev_ts: float | None = time.time()
        d = psutil.disk_io_counters()
        n = _net_totals()
        self._disk = (d.read_bytes, d.write_bytes) if d else (0, 0)
        self._net = n if n else (0, 0)
        psutil.cpu_percent(interval=None)  # prime the non-blocking window

    @staticmethod
    def _delta(cur: int, prev: int, dt: float) -> float:
        return max((cur - prev) / dt, 0.0)

    def sample(self) -> dict:
        now = time.time()
        dt = max(now - (self._prev_ts or now), 1e-6)
        self._prev_ts = now

        cpu_pct = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count() or 1

        try:
            load1, load5, load15 = os.getloadavg()
        except OSError:
            load1 = load5 = load15 = None

        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()

        try:
            du = psutil.disk_usage(_ROOT)
            disk_total, disk_used, disk_pct = float(du.total), float(du.used), float(du.percent)
        except OSError:
            disk_total = disk_used = disk_pct = None

        d = psutil.disk_io_counters()
        n = _net_totals()
        disk_read = disk_write = net_recv = net_sent = None
        if d:
            disk_read = self._delta(d.read_bytes, self._disk[0], dt)
            disk_write = self._delta(d.write_bytes, self._disk[1], dt)
            self._disk = (d.read_bytes, d.write_bytes)
        if n:
            net_recv = self._delta(n[0], self._net[0], dt)
            net_sent = self._delta(n[1], self._net[1], dt)
            self._net = n

        try:
            proc_count = len(psutil.pids())
        except Exception:
            proc_count = None

        return {
            "ts": now,
            "cpu_pct": cpu_pct,
            "cpu_count": cpu_count,
            "load1": load1,
            "load5": load5,
            "load15": load15,
            "mem_total": float(vm.total),
            "mem_used": float(vm.used),
            "mem_pct": vm.percent,
            "swap_total": float(sw.total),
            "swap_used": float(sw.used),
            "disk_total": disk_total,
            "disk_used": disk_used,
            "disk_pct": disk_pct,
            "disk_read": disk_read,
            "disk_write": disk_write,
            "net_recv": net_recv,
            "net_sent": net_sent,
            "uptime": now - psutil.boot_time(),
            "proc_count": proc_count,
        }
