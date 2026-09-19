"""Read-only host security facts for the security page."""
from __future__ import annotations
import re, subprocess, time
from pathlib import Path
from .config import config
ROOT = Path(config.host_root or "/")
def _run(command: list[str], timeout: float = 4) -> tuple[str, str | None]:
    try: r = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
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
        if path.exists(): return _run([str(path), *args])
    return "", f"{binary} is not installed on the host"
def _file(path: str, limit: int = 80) -> tuple[str, str | None]:
    try: return "\n".join(_host(path).read_text(errors="replace").splitlines()[:limit]), None
    except OSError as exc: return "", str(exc)
def _ufw_status() -> tuple[str, str | None]:
    conf, ce = _file("/etc/ufw/ufw.conf", 20); rules, re_ = _file("/etc/ufw/user.rules", 80)
    if ce and re_: return "", ce
    out=[f"Status: {'active' if 'ENABLED=yes' in conf else 'inactive'}"]
    if rules: out += ["User rules:", *rules.splitlines()]
    return "\n".join(out), re_ if not rules else None
def _matches(rows: list[str], pattern: str): return [r for r in rows if re.search(pattern,r,re.I)]
def snapshot() -> dict:
    ufw, ufwe = _ufw_status(); ipt, ipte = _file("/etc/ufw/user.rules"); nft, nfte = _file("/etc/nftables.conf"); sockets, socketse = _run_host_binary("ss", ["-lntup"]); auth=_tail(["/var/log/auth.log","/var/log/secure"])
    try: ssh=[x.strip() for x in _host("/etc/ssh/sshd_config").read_text(errors="replace").splitlines() if x.strip() and not x.lstrip().startswith("#")]
    except OSError: ssh=[]
    return {"collected_at":time.time(),"read_only":True,"firewall":{"ufw":{"output":ufw,"error":ufwe},"iptables":{"rules":ipt.splitlines()[:80],"error":ipte},"nftables":{"rules":nft.splitlines()[:80],"error":nfte}},"ssh":{"auth_log":auth,"config":ssh},"listeners":{"lines":sockets.splitlines()[:100],"error":socketse},"signals":{"failed_auth":_matches(auth,r"failed password|authentication failure|invalid user"),"accepted_auth":_matches(auth,r"accepted (password|publickey)")}}
