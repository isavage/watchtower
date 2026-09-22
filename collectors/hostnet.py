"""Host network facts read from the bind-mounted host /proc and /sys.

A container has its own network namespace, so psutil's ioctl/getifaddrs-based
APIs (``net_if_stats``, ``net_if_addrs``) only ever see the container's single
veth with its Docker bridge IP. The host's real interfaces, counters, MTU,
link speed and addresses are all plain files under the mounts declared in
docker-compose.yml, which this module parses.

Every function degrades to ``None``/``[]`` when the mounts are absent (local
dev), letting callers fall back to psutil.
"""
from __future__ import annotations

import ipaddress
import os
import time

from .hostconfig import host_config

_ADDR_TTL = 15.0
_addr_cache: tuple[float, list[dict]] | None = None


def host_mode() -> bool:
    """True when we are reading the host's /proc (Docker deployment)."""
    return host_config.uses_host_proc


def _proc(*parts: str) -> str:
    # GOTCHA: /proc/net is a symlink to /proc/self/net, which the kernel
    # resolves in the *reader's* namespace — so /host/proc/net/dev from
    # inside the container is still the container's own view. PID 1 is the
    # host's init (pid: host), so /host/proc/1/net/* genuinely reaches the
    # host network namespace.
    if host_config.uses_host_proc and parts and parts[0] == "net":
        return os.path.join(host_config.proc_path, "1", "net", *parts[1:])
    return os.path.join(host_config.proc_path, *parts)


def _sys(*parts: str) -> str:
    root = host_config.proc_path[: -len("/proc")] if host_config.uses_host_proc else ""
    return os.path.join(root, "sys", *parts)


def host_mounts() -> list[tuple[str, str, str]] | None:
    """(device, mountpoint, fstype) from the HOST mount namespace.

    GOTCHA: /proc/mounts is a symlink to /proc/self/mounts (reader's
    namespace), so PID 1's mounts must be read directly, like the net files.
    """
    if not host_config.uses_host_proc:
        return None
    try:
        with open(os.path.join(host_config.proc_path, "1", "mounts")) as fh:
            text = fh.read()
    except OSError:
        return None
    rows: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        f = line.split()
        if len(f) < 3:
            continue
        mnt = f[1].replace("\\040", " ").replace("\\011", "\t")
        rows.append((f[0], mnt, f[2]))
    return rows or None


def net_dev() -> dict[str, dict] | None:
    """Per-interface byte/packet counters from /proc/net/dev.

    Returns None when the file cannot be read, so callers can fall back.
    """
    try:
        with open(_proc("net", "dev")) as fh:
            text = fh.read()
    except OSError:
        return None
    out: dict[str, dict] = {}
    for line in text.splitlines():
        name, sep, rest = line.partition(":")
        if not sep:
            continue
        f = rest.split()
        if len(f) < 16:
            continue
        try:
            out[name.strip()] = {
                "rx_bytes": int(f[0]),
                "rx_packets": int(f[1]),
                "rx_errs": int(f[2]),
                "rx_drop": int(f[3]),
                "tx_bytes": int(f[8]),
                "tx_packets": int(f[9]),
                "tx_errs": int(f[10]),
                "tx_drop": int(f[11]),
            }
        except ValueError:
            continue
    return out or None


def hostname() -> str | None:
    """The host's hostname, from /proc/sys/kernel/hostname in its namespace."""
    try:
        with open(_proc("sys", "kernel", "hostname")) as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def link_info(name: str) -> dict:
    """up / link speed / mtu for one interface from /sys/class/net/<name>."""

    def read(field: str) -> str | None:
        try:
            with open(_sys("class", "net", name, field)) as fh:
                return fh.read().strip()
        except OSError:
            return None

    try:
        speed = int(read("speed") or "")
    except ValueError:
        speed = -1  # file missing, or "-1"/"invalid" while the link is down
    carrier = read("carrier")  # absent on some virtual drivers
    up = carrier == "1" if carrier is not None else read("operstate") == "up"
    try:
        mtu: int | None = int(read("mtu") or "")
    except ValueError:
        mtu = None
    return {
        "up": up,
        "speed_mbps": float(speed) if speed > 0 else None,
        "mtu": mtu,
    }


def local_addresses() -> list[dict]:
    """IPv4 + IPv6 addresses in the host namespace, tagged with interface names.

    IPv4: /proc/net/fib_trie marks local addresses ("/32 host LOCAL") but not
    their interface, so each is matched against the subnets in
    /proc/net/route (falling back to the default-route interface).
    IPv6: /proc/net/if_inet6 lists address *and* interface directly.

    Result is cached briefly; these files change rarely and the page polls.
    """
    global _addr_cache
    now = time.time()
    if _addr_cache and now - _addr_cache[0] < _ADDR_TTL:
        return _addr_cache[1]

    out: list[dict] = []
    try:
        with open(_proc("net", "fib_trie")) as fh:
            trie = fh.read()
    except OSError:
        trie = ""
    try:
        with open(_proc("net", "route")) as fh:
            route = fh.read()
    except OSError:
        route = ""
    nets, default_iface = _route_networks(route)

    seen: set[str] = set()
    lines = trie.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith("|-- "):
            continue
        ip = s[4:].strip()
        if not ip or ":" in ip:  # IPv6 comes from if_inet6, with iface names
            continue
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if not nxt.startswith("/32 host"):
            continue
        try:
            addr = ipaddress.IPv4Address(ip)
        except ValueError:
            continue
        if addr.is_loopback or ip in seen:
            continue
        seen.add(ip)
        out.append(
            {
                "iface": _match_iface(addr, nets) or default_iface or "?",
                "family": "AF_INET",
                "address": ip,
            }
        )

    try:
        with open(_proc("net", "if_inet6")) as fh:
            v6 = fh.read()
    except OSError:
        v6 = ""
    for line in v6.splitlines():
        # Fields: address ifindex prefix_len scope flags ifname
        f = line.split()
        if len(f) < 6:
            continue
        hexaddr, scope, iface = f[0], f[3], f[5]
        try:
            if int(scope, 16) == 0x20:  # link-local: noise on a dashboard
                continue
            addr = ipaddress.IPv6Address(
                ":".join(hexaddr[j : j + 4] for j in range(0, 32, 4))
            )
        except ValueError:
            continue
        if addr.is_loopback:
            continue
        out.append({"iface": iface, "family": "AF_INET6", "address": str(addr)})

    _addr_cache = (now, out)
    return out


def _route_networks(route: str) -> tuple[list[tuple[ipaddress.IPv4Network, str]], str | None]:
    """(subnet, iface) rows plus the default-route interface from /proc/net/route."""
    nets: list[tuple[ipaddress.IPv4Network, str]] = []
    default_iface: str | None = None
    for line in route.splitlines()[1:]:
        f = line.split()
        if len(f) < 8:
            continue
        iface, dest, mask = f[0], f[1], f[7]
        if dest == "00000000":
            if mask == "00000000":
                default_iface = iface
            continue
        try:
            # Hex is printed in little-endian byte order on Linux.
            net = ipaddress.IPv4Network(
                (
                    int.from_bytes(bytes.fromhex(dest)[::-1], "big"),
                    int.from_bytes(bytes.fromhex(mask)[::-1], "big"),
                ),
                strict=False,
            )
        except (ValueError, TypeError):
            continue
        nets.append((net, iface))
    return nets, default_iface


def _match_iface(addr: ipaddress.IPv4Address, nets) -> str | None:
    for net, iface in nets:
        if addr in net:
            return iface
    return None
