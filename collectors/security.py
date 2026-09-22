"""Read-only host security facts for the Security page."""
from __future__ import annotations
import ipaddress
import os
import re, time
from pathlib import Path
from . import hostnet
from .hostconfig import host_config
ROOT = Path(host_config.host_root or "/")
def _host(path: str) -> Path: return ROOT / path.lstrip("/") if host_config.host_root else Path(path)
def _tail(names: list[str], limit: int = 80) -> list[str]:
    for name in names:
        try:
            rows=[x.rstrip() for x in _host(name).open(errors="replace") if x.strip()]
            if rows: return rows[-limit:]
        except OSError: pass
    return []
def _file(path: str, limit: int = 80) -> tuple[str, str | None]:
    try: return "\n".join(_host(path).read_text(errors="replace").splitlines()[:limit]), None
    except OSError as exc: return "", str(exc)
def _ufw_status() -> tuple[str, str | None]:
    conf, ce = _file("/etc/ufw/ufw.conf", 20); defaults, de = _file("/etc/default/ufw", 40); rules, re_ = _file("/etc/ufw/user.rules", 240)
    if ce and re_: return "", ce
    status = "active" if "ENABLED=yes" in conf else "inactive"
    readable=[]
    policies = []
    policy_words = {"ACCEPT": "allow", "DROP": "deny", "REJECT": "deny", "REFUSE": "deny"}
    for line in defaults.splitlines():
        # values are quoted: DEFAULT_INPUT_POLICY="DROP"
        match = re.match(r'DEFAULT_(INPUT|OUTPUT|FORWARD)_POLICY="?(\w+)"?', line)
        if match:
            word = policy_words.get(match.group(2).upper(), match.group(2).lower())
            policies.append(f"default {match.group(1).lower()}: {word}")
    for line in rules.splitlines():
        if "ACCEPT" not in line: continue
        pmatch = re.search(r"-p\s+(tcp|udp)", line, re.I)
        proto = pmatch.group(1).lower() if pmatch else "tcp"
        match=re.search(r"--dports?\s+([0-9][0-9,:-]*)", line)
        if match: readable.append(f"allow {proto} {match.group(1)}")
    return f"Status: {status}\n" + ("\n".join(dict.fromkeys(policies + readable)) if (policies or readable) else "No readable user port rules found."), re_ if not rules else None
def _matches(rows: list[str], pattern: str): return [r for r in rows if re.search(pattern,r,re.I)]
def _hex_addr(addr: str) -> str:
    """Decode a /proc/net hex address (little-endian 32-bit words) to readable form."""
    try:
        if len(addr) == 8:
            return ".".join(str(b) for b in bytes.fromhex(addr)[::-1])
        if len(addr) == 32:
            words = (addr[i:i+8] for i in range(0, 32, 8))
            raw = b"".join(bytes.fromhex(w)[::-1] for w in words)
            return str(ipaddress.IPv6Address(raw))
    except ValueError: pass
    return addr
def _parse_proc_net_listeners() -> tuple[list[str], str | None]:
    """LISTEN sockets in the host namespace via hostnet._proc (see its GOTCHA)."""
    lines=[]
    for proto in ["tcp", "tcp6", "udp", "udp6"]:
        listen_states = {"0A"} if proto.startswith("tcp") else {"07"}
        try:
            with open(hostnet._proc("net", proto)) as fh:
                for row in fh:
                    f=row.split()
                    if len(f)<10 or f[3] not in listen_states: continue
                    local=f[1]
                    if ":" not in local: continue
                    addr,port=local.rsplit(":",1)
                    if not port: continue
                    try: port=int(port,16)
                    except ValueError: continue
                    lines.append(f"{proto.upper()} LISTEN {_hex_addr(addr)}:{port}")
        except OSError: pass
    return lines, None if lines else "No listening sockets found in the host network namespace."

# Keywords where sshd keeps every occurrence (or where each line opens a new
# conditional scope) instead of applying first-value-wins.
_SSH_MULTI = {"acceptenv", "allowgroups", "allowusers", "denygroups", "denyusers",
              "hostkey", "identityfile", "listenaddress", "subsystem", "match"}
def _ssh_config() -> tuple[list[str], str | None]:
    """Effective sshd settings, resolved per sshd(8): the FIRST obtained value
    of each keyword wins, Include is processed in place, and Match sections
    scope their own settings. Shadowed duplicates are reported as ignored."""
    root = _host("/etc/ssh/sshd_config")
    if not root.is_file(): return [], f"{root} not found"
    entries: list[tuple[str, str, str, str]] = []  # (file label, kw, raw, scope)
    visited: set[str] = set()
    def label(path: Path) -> str:
        try: return str(path.relative_to(_host("/etc/ssh")))
        except ValueError: return path.name
    def parse(path: Path, scope: str) -> None:
        try: visited.add(str(path.resolve()))
        except OSError: return
        try: text = path.read_text(errors="replace")
        except OSError: return
        lbl = label(path)
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"): continue
            parts = re.split(r"[=\s]+", s, maxsplit=1)
            kw, arg = parts[0], parts[1] if len(parts) > 1 else ""
            k = kw.lower()
            if k == "include":
                for pattern in (arg or "").split():
                    base = _host(pattern) if pattern.startswith("/") else _host(f"/etc/ssh/{pattern}")
                    try: found = sorted(base.parent.glob(base.name))
                    except OSError: continue
                    for f in found:
                        try:
                            if str(f.resolve()) in visited: continue
                        except OSError: pass
                        parse(f, scope)
                continue
            if k == "match":
                scope = f"Match {arg or '?'}"
                entries.append((lbl, k, s, scope))
                continue
            entries.append((lbl, k, s, scope))
    parse(root, "global")
    seen: dict[tuple[str, str], str] = {}
    effective: list[str] = []
    ignored: list[str] = []
    for lbl, k, s, scope in entries:
        if k == "match":
            effective.append(f"[{lbl}] {s}")
            continue
        key = (scope, k)
        if k not in _SSH_MULTI and key in seen:
            ignored.append(f"ignored: {s} ({lbl}) — overridden by {seen[key]}")
            continue
        seen.setdefault(key, lbl)
        prefix = "" if scope == "global" else f"{scope} \u2192 "
        effective.append(f"{prefix}{s}  [{lbl}]")
    return effective + ignored, None
def _sshd_process() -> str | None:
    """Presence of a running sshd, via the shared host PID namespace.

    Deliberately reads only /proc/<pid>/comm — never cmdline or environ: with
    `pid: host` those can expose other users' secrets (argv frequently carries
    tokens/passwords) and none of it is needed to answer "is sshd running?".
    """
    try: pids = [p for p in os.listdir(host_config.proc_path) if p.isdigit()]
    except OSError: return None
    for pid in pids:
        try:
            with open(os.path.join(host_config.proc_path, pid, "comm")) as fh:
                if fh.read().strip() == "sshd": return "sshd"
        except OSError: continue
    return None
def snapshot() -> dict:
    ufw, ufwe = _ufw_status(); ipt, ipte = _file("/etc/ufw/user.rules"); nft, nfte = _file("/etc/nftables.conf"); sockets, socketse = _parse_proc_net_listeners(); auth=_tail(["/var/log/auth.log","/var/log/secure"])
    ssh, ssh_err = _ssh_config(); sshd_proc = _sshd_process()
    # Derived JSON only: the raw log tail and even the matched lines (which
    # carry usernames/IPs) stay inside this function — the UI renders counts,
    # so counts are all that leave the process. A stolen UI session must not
    # be able to read auth.log.
    failed = _matches(auth, r"failed password|authentication failure|invalid user")
    accepted = _matches(auth, r"accepted (password|publickey)")
    return {"collected_at":time.time(),"read_only":True,"firewall":{"ufw":{"output":ufw,"error":ufwe},"iptables":{"rules":ipt.splitlines()[:80],"error":ipte},"nftables":{"rules":nft.splitlines()[:80],"error":nfte}},"ssh":{"config":ssh,"config_error":ssh_err,"process":sshd_proc},"listeners":{"lines":sockets[:100],"error":socketse},"signals":{"failed_count":len(failed),"accepted_count":len(accepted)}}
