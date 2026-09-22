"""Runtime configuration, sourced from environment variables."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Config:
    db_path: str = field(default_factory=lambda: _env("WT_DB_PATH", "data/watchtower.db"))
    admin_user: str = field(default_factory=lambda: _env("WT_ADMIN_USER", "admin"))
    admin_password: str = field(default_factory=lambda: _env("WT_ADMIN_PASSWORD", "changeme"))
    secret_key: str = field(default_factory=lambda: _env("WT_SECRET_KEY", ""))
    sample_interval: float = field(default_factory=lambda: float(_env("WT_SAMPLE_INTERVAL", "2")))
    session_days: int = field(default_factory=lambda: int(_env("WT_SESSION_DAYS", "7")))
    cookie_secure: bool = field(default_factory=lambda: _env("WT_COOKIE_SECURE", "auto").lower() in ("1", "true", "yes"))
    docker_socket: str = field(default_factory=lambda: _env("WT_DOCKER_SOCKET", "/var/run/docker.sock"))
    # When set, host facts come from the watchtower-host-proxy sidecar over
    # the network instead of local /proc mounts (the Docker deployment has
    # no host mounts at all). Empty = read this machine directly (dev).
    host_proxy_url: str = field(default_factory=lambda: _env("WT_HOST_PROXY_URL", ""))
    host_proxy_token: str = field(default_factory=lambda: _env("WT_HOST_PROXY_TOKEN", ""))

    def __post_init__(self) -> None:
        # A missing secret means we are not behind a deliberate config; generate
        # an ephemeral one so sessions still work in dev (they reset on restart).
        if not self.secret_key or self.secret_key == "please-change-me":
            self.secret_key = secrets.token_hex(32)
            self._secret_is_ephemeral = True
        else:
            self._secret_is_ephemeral = False


config = Config()
