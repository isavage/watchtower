"""Where the host's filesystem lives for the collectors.

Shared by both deployment modes:

* host-proxy container: ``WT_HOST_ROOT=/host`` with the /proc and /sys
  bind-mounts from docker-compose.yml.
* app container in Docker: unset — the app never reads hosts files there, it
  queries the proxy instead.
* local dev (single process): unset → collectors read this machine directly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class HostConfig:
    host_root: str = field(default_factory=lambda: os.environ.get("WT_HOST_ROOT", "").strip())

    @property
    def proc_path(self) -> str:
        """Where to read /proc from — the host's when mounted, else our own."""
        if self.host_root:
            p = os.path.join(self.host_root, "proc")
            if os.path.isdir(p):
                return p
        return "/proc"

    @property
    def uses_host_proc(self) -> bool:
        return self.proc_path != "/proc"


host_config = HostConfig()
