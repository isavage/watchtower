"""Read-only VPS operations and security overview."""
from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

import psutil
from fastapi import APIRouter, Depends

from .. import auth
from ..config import config

router = APIRouter(prefix="/api/ops", tags=["operations"], dependencies=[Depends(auth.current_user)])
ROOT = Path(config.host_root or "/")


def run(cmd: list[str], timeout: float = 3) -> tuple[str, str | None]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", str(exc)
    if result.returncode != 0:
        return result.stdout.strip(), result.stderr.strip() or f"exit {result.returncode}"
    return result.stdout.strip(), None


def lines(value: str, limit: int = 100) -> list[str]:
    return [line for line in value.splitlines() if line.strip()][:limit]


def read_host_log(name: str, limit: int = 30) -> list[str]:
    path = ROOT / "var/log" / name if config.host_root else Path("/var/log") / name
    try:
        with path.open(errors="replace") as handle:
            return [line.rstrip() for line in handle.readlines()[-limit:] if line.strip()]
    except OSError:
        return []


def parse_login_lines(rows: list[str]) -> list[dict[str, str]]:
    result = []
    for row in rows:
        parts = row.split()
        if len(parts) >= 4 and parts[0] not in {"wtmp", "btmp", "reboot", "shutdown"}:
            result.append({"user": parts[0], "source": parts[2] if len(parts) > 2 else "—", "when": " ".join(parts[3:])})
    return result


def login_history() -> dict:
    successful, success_error = run(["last", "-ai", "-n", "30"])
    failed, failed_error = run(["lastb", "-ai", "-n", "30"])
    # last/lastb may be absent from the container; fall back to host auth logs.
    secure = read_host_log("secure") or read_host_log("auth.log")
    failed_rows = parse_login_lines(lines(failed, 30)) if failed else []
    recent_rows = parse_login_lines(lines(successful, 30)) if successful else []
    return {
        "recent": recent_rows,
        "failed": failed_rows,
        "auth_log_tail": secure,
        "status": "ok" if recent_rows or failed_rows or secure else "unavailable",
        "errors": [error for error in (success_error, failed_error) if error],
    }


def firewall() -> dict:
    result = {}
    for name, command in (("ufw", ["ufw", "status", "verbose"]), ("nftables", ["nft", "list", "ruleset"]), ("iptables", ["iptables", "-S"])):
        output, error = run(command)
        result[name] = {"available": bool(output), "status": lines(output, 80), "error": error}
    return result


def snapshot() -> dict:
    vm = psutil.virtual_memory()
    du = psutil.disk_usage(str(ROOT))
    listeners = []
    try:
        for connection in psutil.net_connections(kind="inet"):
            if connection.status == "LISTEN" and connection.laddr:
                listeners.append({"address": f"{connection.laddr.ip}:{connection.laddr.port}", "pid": connection.pid})
    except (psutil.Error, PermissionError) as exc:
        listener_error = str(exc)
    else:
        listener_error = None

    containers, docker_error = run(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}|{{.Ports}}"])
    services, systemd_error = run(["systemctl", "--failed", "--no-legend", "--plain"])
    return {
        "security": firewall(),
        "ssh": login_history(),
        "listeners": {"items": listeners, "error": listener_error},
        "services": {
            "docker": [dict(zip(["name", "status", "ports"], row.split("|", 2))) for row in lines(containers)],
            "docker_error": docker_error,
            "failed_systemd": lines(services, 40),
            "systemd_error": systemd_error,
        },
        "health": {"memory_pct": vm.percent, "disk_pct": du.percent, "load": list(os.getloadavg()) if hasattr(os, "getloadavg") else [], "temperatures": []},
        "storage": {"root": {"total": du.total, "used": du.used, "free": du.free, "pct": du.percent}},
        "metadata": {"hostname": socket.gethostname(), "collected_at": time.time(), "read_only": True},
    }


@router.get("")
def ops_snapshot() -> dict:
    return snapshot()
