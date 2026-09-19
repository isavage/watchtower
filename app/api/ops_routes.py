"""Read-only VPS operations and security overview."""
from __future__ import annotations
import os, re, shutil, socket, subprocess, time
from pathlib import Path
import psutil
from fastapi import APIRouter, Depends
from .. import auth
from ..config import config

router = APIRouter(prefix="/api/ops", tags=["operations"], dependencies=[Depends(auth.current_user)])
ROOT = Path(config.host_root or "/")

def run(cmd: list[str], timeout: float = 3) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""

def lines(value: str, limit: int = 100) -> list[str]:
    return [x for x in value.splitlines() if x.strip()][:limit]

def host_path(path: str) -> Path:
    return ROOT / path.lstrip("/") if config.host_root else Path(path)

def logins() -> list[dict]:
    out = run(["last", "-ai", "-n", "30"])
    result=[]
    for row in lines(out, 30):
        if row.startswith(("wtmp", "reboot", "shutdown")): continue
        parts=row.split()
        if len(parts) >= 5:
            result.append({"user": parts[0], "source": parts[2] if parts[1] in ("pts/0","pts/1","tty1") else parts[1], "when":" ".join(parts[3:])})
    return result

def failed_logins() -> list[dict]:
    out=run(["lastb", "-ai", "-n", "30"])
    result=[]
    for row in lines(out,30):
        parts=row.split()
        if len(parts)>=4 and parts[0] not in ("btmp",): result.append({"user":parts[0],"source":parts[2] if len(parts)>2 else "—","when":" ".join(parts[3:])})
    return result

def firewall() -> dict:
    ufw=run(["ufw","status","verbose"])
    nft=run(["nft","list","ruleset"])
    ipt=run(["iptables","-S"])
    return {"ufw":{"available":bool(ufw),"status":lines(ufw,40)},"nftables":{"available":bool(nft),"rules":len(lines(nft,500))},"iptables":{"available":bool(ipt),"rules":lines(ipt,60)}}

def snapshot() -> dict:
    vm=psutil.virtual_memory(); du=psutil.disk_usage(str(ROOT))
    listeners=[]
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.status=="LISTEN" and c.laddr: listeners.append({"address":f"{c.laddr.ip}:{c.laddr.port}","pid":c.pid})
    except (psutil.Error, PermissionError): pass
    containers=run(["docker","ps","-a","--format","{{.Names}}|{{.Status}}|{{.Ports}}"])
    services=run(["systemctl","--failed","--no-legend","--plain"])
    ports=run(["ss","-tuln"])
    return {"security":firewall(),"ssh":{"recent":logins(),"failed":failed_logins(),"config":{k:run(["sshd","-T"] ) for k in []}},"listeners":listeners,"services":{"docker":[dict(zip(["name","status","ports"],x.split("|",2))) for x in lines(containers)],"failed_systemd":lines(services,40)},"health":{"memory_pct":vm.percent,"disk_pct":du.percent,"disk_free":du.free,"load":os.getloadavg() if hasattr(os,"getloadavg") else [],"temperatures":[]},"storage":{"root":{"total":du.total,"used":du.used,"free":du.free,"pct":du.percent}},"metadata":{"hostname":socket.gethostname(),"collected_at":time.time(),"read_only":True}}

@router.get("")
def ops_snapshot() -> dict: return snapshot()
