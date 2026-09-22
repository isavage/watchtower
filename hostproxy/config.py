"""watchtower-host-proxy runtime configuration.

Deliberately separate from ``app.config`` (the UI app's settings): this
service owns only host-access policy — the bearer token and a per-endpoint
allow-list, mirroring the tecnativa docker-socket-proxy model where each
capability is switched on individually and everything else stays denied.

Defaults are deny-safe:

* ``WT_HOST_PROXY_TOKEN`` — empty by default, and an empty token means every
  data endpoint answers 503 (fail closed: a misconfigured proxy serves
  nothing rather than everything).
* ``WT_ALLOW_METRICS`` / ``WT_ALLOW_DETAILS`` — on by default (the dashboard
  needs them).
* ``WT_ALLOW_SECURITY`` — OFF by default: it is the only endpoint whose data
  comes from the /etc and /var/log mounts, so those mounts should only be
  declared when the flag is actually used.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _allow(name: str, default: str) -> bool:
    return _env(name, default).lower() in ("1", "true", "yes")


@dataclass
class ProxyConfig:
    token: str = field(default_factory=lambda: _env("WT_HOST_PROXY_TOKEN", ""))
    allow_metrics: bool = field(default_factory=lambda: _allow("WT_ALLOW_METRICS", "1"))
    allow_details: bool = field(default_factory=lambda: _allow("WT_ALLOW_DETAILS", "1"))
    allow_security: bool = field(default_factory=lambda: _allow("WT_ALLOW_SECURITY", "0"))

    def allow_map(self) -> dict[str, bool]:
        return {
            "metrics": self.allow_metrics,
            "details": self.allow_details,
            "security": self.allow_security,
        }


proxy_config = ProxyConfig()
