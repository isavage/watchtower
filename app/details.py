"""Fine-grained, live (non-historised) system detail for the drill-down pages.

Everything here is read on demand from psutil against the host /proc, so the
per-core / per-process / per-disk views reflect the VPS rather than the
container.
"""
from __future__ import annotations

import platform
import time

import psutil

from .collector import _ROOT

_HZ = psutil.cpu_freq()  # touched once so psutil caches the path lookup


class ProcTracker:
    """Keeps live psutil handles so cpu_percent() has a window to diff over.

    A fresh ``Process`` always reports 0% CPU on its first call, so we retain
    the objects between samples and drop the ones that exited.
    """

    def __init__(self) -> None:
        self._procs: dict[int, psutil.Process] = {}

    def snapshot(self, limit: int = 15) -> dict:
        now = time.time()
        alive: set[int] = set()
        rows: list[dict] = []

        for pid in psutil.pids():
            proc = self._procs.get(pid)
            if proc is None:
                try:
                    proc = psutil.Process(pid)
                except psutil.Error:
                    continue
                self._procs[pid] = proc
            try:
                with proc.oneshot():
                    cpu = proc.cpu_percent(interval=None)
                    mem_info = proc.memory_info()
                    status = proc.status()
                    name = proc.name()
                    cmdline = " ".join(proc.cmdline()[:6])
                    username = proc.username()
                    create = proc.create_time()
                    num_threads = proc.num_threads()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # AccessDenied is common in a container without full privileges;
                # the pid is still alive, so keep the handle around.
                if isinstance(proc, psutil.Process):
                    alive.add(pid)
                continue
            except psutil.Error:
                continue

            alive.add(pid)
            rows.append(
                {
                    "pid": pid,
                    "name": name,
                    "user": username,
                    "cpu_pct": cpu,
                    "mem_rss": float(mem_info.rss),
                    "mem_vms": float(mem_info.vms),
                    "mem_pct": proc.memory_percent(),
                    "status": status,
                    "threads": num_threads,
                    "started": create,
                    "age": max(now - create, 0.0),
                    "cmdline": cmdline[:200],
                }
            )

        # Forget handles for processes that are gone.
        for dead in self._procs.keys() - alive:
            self._procs.pop(dead, None)

        total_mem = psutil.virtual_memory().total or 1.0
        for r in rows:
            r["mem_pct"] = r["mem_rss"] / total_mem * 100.0

        by_cpu = sorted(rows, key=lambda r: r["cpu_pct"], reverse=True)[:limit]
        by_mem = sorted(rows, key=lambda r: r["mem_rss"], reverse=True)[:limit]
        return {
            "count": len(rows),
            "total_mem": float(total_mem),
            "top_cpu": by_cpu,
            "top_mem": by_mem,
        }


_tracker = ProcTracker()


def _per_core() -> list[dict]:
    percents = psutil.cpu_percent(interval=None, percpu=True)
    try:
        times = psutil.cpu_times_percent(interval=None, percpu=True)
    except Exception:
        times = []
    out = []
    for i, pct in enumerate(percents):
        row = {"core": i, "pct": pct}
        if i < len(times):
            t = times[i]
            row.update(
                user=t.user,
                system=t.system,
                idle=t.idle,
                iowait=getattr(t, "iowait", 0.0),
            )
        out.append(row)
    return out


def _cpu_breakdown() -> dict:
    t = psutil.cpu_times_percent(interval=None)
    keys = ("user", "system", "idle", "iowait", "irq", "softirq", "steal", "guest", "guest_nice")
    return {k: getattr(t, k, 0.0) for k in keys}


def _memory() -> dict:
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return {
        "total": float(vm.total),
        "available": float(vm.available),
        "used": float(vm.used),
        "free": float(vm.free),
        "pct": vm.percent,
        "active": float(vm.active),
        "inactive": float(vm.inactive),
        "buffers": float(getattr(vm, "buffers", 0)),
        "cached": float(getattr(vm, "cached", 0)),
        "shared": float(getattr(vm, "shared", 0)),
        "swap_total": float(sw.total),
        "swap_used": float(sw.used),
        "swap_pct": sw.percent,
    }


def _partitions() -> list[dict]:
    out = []
    for p in psutil.disk_partitions(all=False):
        # Inside the container the host fs is remapped under /host.
        mount = p.mountpoint
        try:
            du = psutil.disk_usage(mount)
        except (PermissionError, OSError):
            try:
                du = psutil.disk_usage(_ROOT + mount)
            except OSError:
                continue
        out.append(
            {
                "device": p.device,
                "mountpoint": mount,
                "fstype": p.fstype,
                "total": float(du.total),
                "used": float(du.used),
                "free": float(du.free),
                "pct": du.percent,
            }
        )
    return out


def _disks() -> dict:
    io = psutil.disk_io_counters(perdisk=True) or {}
    totals = psutil.disk_io_counters()
    now = time.time()
    prev = _disks.__dict__.get("_prev") or {}
    prev_ts = _disks.__dict__.get("_ts") or now
    dt = max(now - prev_ts, 1e-6)
    _disks.__dict__["_prev"] = {k: (v.read_bytes, v.write_bytes, v.read_count, v.write_count) for k, v in io.items()}
    _disks.__dict__["_ts"] = now

    devices = []
    for name, c in sorted(io.items()):
        p = prev.get(name)
        row = {
            "name": name,
            "read_total": float(c.read_bytes),
            "write_total": float(c.write_bytes),
            "read_count": int(c.read_count),
            "write_count": int(c.write_count),
        }
        if p:
            row["read_rate"] = max((c.read_bytes - p[0]) / dt, 0.0)
            row["write_rate"] = max((c.write_bytes - p[1]) / dt, 0.0)
            row["ops"] = max((c.read_count - p[2] + c.write_count - p[3]) / dt, 0.0)
        devices.append(row)

    return {
        "devices": devices,
        "total": {
            "read": float(totals.read_bytes) if totals else 0.0,
            "write": float(totals.write_bytes) if totals else 0.0,
        }
        if totals
        else None,
    }


def _nics() -> dict:
    stats = psutil.net_if_stats()
    io = psutil.net_io_counters(pernic=True)
    now = time.time()
    prev = _nics.__dict__.get("_prev") or {}
    prev_ts = _nics.__dict__.get("_ts") or now
    dt = max(now - prev_ts, 1e-6)
    _nics.__dict__["_prev"] = {k: (v.bytes_sent, v.bytes_recv) for k, v in io.items()}
    _nics.__dict__["_ts"] = now

    out = []
    for name, c in sorted(io.items()):
        if name == "lo":
            continue
        s = stats.get(name)
        p = prev.get(name)
        row = {
            "name": name,
            "up": bool(s.isup) if s else None,
            "speed_mbps": float(s.speed) if s and s.speed else None,
            "mtu": int(s.mtu) if s else None,
            "recv_total": float(c.bytes_recv),
            "sent_total": float(c.bytes_sent),
            "packets_err": int(c.errin + c.errout),
            "packets_drop": int(c.dropin + c.dropout),
        }
        if p:
            row["recv_rate"] = max((c.bytes_recv - p[1]) / dt, 0.0)
            row["sent_rate"] = max((c.bytes_sent - p[0]) / dt, 0.0)
        out.append(row)
    out.sort(key=lambda r: -(r.get("recv_rate") or 0.0))
    return {"interfaces": out}


def _addresses() -> list[dict]:
    out = []
    for name, addrs in psutil.net_if_addrs().items():
        if name == "lo":
            continue
        for a in addrs:
            if a.family.name in ("AF_INET", "AF_INET6"):
                out.append({"iface": name, "family": a.family.name, "address": a.address})
    return out


def details(limit: int = 15) -> dict:
    try:
        boot = psutil.boot_time()
    except Exception:
        boot = None
    return {
        "ts": time.time(),
        "host": {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "arch": platform.machine(),
            "boot_time": boot,
            "uptime": (time.time() - boot) if boot else None,
        },
        "cpu": {
            "count_logical": psutil.cpu_count(logical=True),
            "count_physical": psutil.cpu_count(logical=False),
            "per_core": _per_core(),
            "breakdown": _cpu_breakdown(),
            "freq": (lambda f: {"current": f.current, "min": f.min, "max": f.max} if f else None)(
                psutil.cpu_freq()
            ),
        },
        "memory": _memory(),
        "processes": _tracker.snapshot(limit),
        "partitions": _partitions(),
        "disk_io": _disks(),
        "network": _nics(),
        "addresses": _addresses(),
    }
