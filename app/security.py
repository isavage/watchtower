"""Read-only host security facts for the security page."""
from __future__ import annotations
import re, subprocess, time
from pathlib import Path
from .config import config

ROOT = Path(config.host_root or "/")

def _run(command: list[str], timeout: float = 4) -> tuple[str, str | None]:
    try:
        r = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", str(exc)
    return r.stdout.strip(), (r.stderr.strip() or f"exit {r.returncode}") if r.returncode else None

def _host(path: str) -> Path: return ROOT / path.lstrip("/") if config.host_root else Path(path)
def _tail(names: list[str], limit: int = 80) -> list[str]:
    for name in names:
        try:
            rows=[x.rstrip() for x in (_host(name)).open(errors="replace") if x.strip()]
            if rows: return rows[-limit:]
        except OSError: pass
    return []
def _net(command: list[str]) -> tuple[str,str|None]:
    if config.host_root:
        nsenter="/usr/bin/nsenter" if Path("/usr/bin/nsenter").exists() else "nsenter"
        return _run([nsenter,"-t","1","-n",*command])
    return _run(command)
def _matches(rows, pattern): return [r for r in rows if re.search(pattern,r,re.I)]
def snapshot() -> dict:
    ufw,ufw_error=_run(["ufw","status","verbose"])
    ipt,ipt_error=_net(["iptables","-S"])
    nft,nft_error=_net(["nft","list","ruleset"])
    sockets,sockets_error=_net(["ss","-lntup"])
    auth=_tail(["/var/log/auth.log","/var/log/secure"])
    ssh_config=[]
    try:
        ssh_config=[x.strip() for x in (_host("/etc/ssh/sshd_config")).read_text(errors="replace").splitlines() if x.strip() and not x.lstrip().startswith("#")]
    except OSError: pass
    return {"collected_at":time.time(),"read_only":True,"firewall":{"ufw":{"output":ufw,"error":ufw_error},"iptables":{"rules":ipt.splitlines()[:80],"error":ipt_error},"nftables":{"rules":nft.splitlines()[:80],"error":nft_error}},"ssh":{"auth_log":auth,"config":ssh_config},"listeners":{"lines":sockets.splitlines()[:100],"error":sockets_error},"signals":{"failed_auth":_matches(auth,r"failed password|authentication failure|invalid user"),"accepted_auth":_matches(auth,r"accepted (password|publickey)")}}
