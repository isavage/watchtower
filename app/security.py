"""Read-only host security facts for the Security page."""
from __future__ import annotations
import ipaddress
import os
import re, subprocess, time
from pathlib import Path
from . import hostnet
from .config import config
ROOT = Path(config.host_root or "/")
def _run(command: list[str], timeout: float = 4, env: dict[str, str] | None = None) -> tuple[str, str | None]:
    try: r = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc: return "", str(exc)
    return r.stdout.strip(), (r.stderr.strip() or f"exit {r.returncode}") if r.returncode else None
def _host(path: str) -> Path: return ROOT / path.lstrip("/") if config.host_root else Path(path)
def _tail(names: list[str], limit: int = 80) -> list[str]:
    for name in names:
        try:
            rows=[x.rstrip() for x in _host(name).open(errors="replace") if x.strip()]
            if rows: return rows[-limit:]
        except OSError: pass
    return []
def _run_host_binary(binary: str, args: list[str]) -> tuple[str, str | None]:
    for path in [ROOT/"usr/sbin"/binary, ROOT/"usr/bin"/binary, ROOT/"bin"/binary, ROOT/"sbin"/binary]:
        if path.exists():
            env = None
            if config.host_root:
                host_lib = str(ROOT / "lib/x86_64-linux-gnu")
                env = {**os.environ, "LD_LIBRARY_PATH": host_lib}
            return _run([str(path), *args], env=env)
    return "", f"{binary} is not installed on the host"
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
        # /etc/default/ufw quotes the values: DEFAULT_INPUT_POLICY="DROP"
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
    """LISTEN sockets in the HOST network namespace.

    GOTCHA: /proc/net is a symlink to /proc/self/net, which the kernel resolves
    in the *reader's* namespace — reading /host/proc/net/tcp from inside the
    container yields the container's own sockets. hostnet._proc() routes
    through /proc/1/net (host init, shared PID namespace) when mounted.
    """
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

def _ssh_config() -> tuple[list[str], str | None]:
    """Effective sshd settings: main file plus any Include'd drop-ins.

    Ubuntu's stock sshd_config is mostly `Include /etc/ssh/sshd_config.d/*.conf`,
    so reading only the main file shows defaults, not the real port/auth config.
    """
    try: raw = _host("/etc/ssh/sshd_config").read_text(errors="replace")
    except OSError as exc: return [], str(exc)
    lines: list[str] = []
    includes: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"): continue
        lines.append(s)
        match = re.match(r"Include\s+(.+)$", s, re.I)
        if match: includes += match.group(1).split()
    for pattern in includes:
        path = _host(pattern) if pattern.startswith("/") else _host(f"/etc/ssh/{pattern}")
        try: files = sorted(path.parent.glob(path.name))
        except OSError: continue
        for f in files:
            try: text = f.read_text(errors="replace")
            except OSError: continue
            for line in text.splitlines():
                s = line.strip()
                if s and not s.startswith("#"): lines.append(f"{f.name}: {s}")
    return lines, None
def _sshd_process() -> str | None:
    """cmdline of a running sshd, found via the shared host PID namespace."""
    try: pids = [p for p in os.listdir(config.proc_path) if p.isdigit()]
    except OSError: return None
    for pid in pids:
        try:
            with open(os.path.join(config.proc_path, pid, "comm")) as fh:
                if fh.read().strip() != "sshd": continue
            with open(os.path.join(config.proc_path, pid, "cmdline"), "rb") as fh:
                cmd = fh.read().replace(b"\x00", b" ").decode(errors="replace").strip()
            return cmd or "sshd"
        except OSError: continue
    return None
def snapshot() -> dict:
    ufw, ufwe = _ufw_status(); ipt, ipte = _file("/etc/ufw/user.rules"); nft, nfte = _file("/etc/nftables.conf"); sockets, socketse = _parse_proc_net_listeners(); auth=_tail(["/var/log/auth.log","/var/log/secure"])
    ssh, ssh_err = _ssh_config(); sshd_proc = _sshd_process()
    return {"collected_at":time.time(),"read_only":True,"firewall":{"ufw":{"output":ufw,"error":ufwe},"iptables":{"rules":ipt.splitlines()[:80],"error":ipte},"nftables":{"rules":nft.splitlines()[:80],"error":nfte}},"ssh":{"auth_log":auth,"config":ssh,"config_error":ssh_err,"process":sshd_proc},"listeners":{"lines":sockets[:100],"error":socketse},"signals":{"failed_auth":_matches(auth,r"failed password|authentication failure|invalid user"),"accepted_auth":_matches(auth,r"accepted (password|publickey)")}}
