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
    host_root: str = field(default_factory=lambda: _env("WT_HOST_ROOT", ""))
    admin_user: str = field(default_factory=lambda: _env("WT_ADMIN_USER", "admin"))
    admin_password: str = field(default_factory=lambda: _env("WT_ADMIN_PASSWORD", "changeme"))
    secret_key: str = field(default_factory=lambda: _env("WT_SECRET_KEY", ""))
    sample_interval: float = field(default_factory=lambda: float(_env("WT_SAMPLE_INTERVAL", "2")))
    session_days: int = field(default_factory=lambda: int(_env("WT_SESSION_DAYS", "7")))
    cookie_secure: bool = field(default_factory=lambda: _env("WT_COOKIE_SECURE", "auto").lower() in ("1", "true", "yes"))

    def __post_init__(self) -> None:
        # A missing secret means we are not behind a deliberate config; generate
        # an ephemeral one so sessions still work in dev (they reset on restart).
        if not self.secret_key or self.secret_key == "please-change-me":
            self.secret_key = secrets.token_hex(32)
            self._secret_is_ephemeral = True
        else:
            self._secret_is_ephemeral = False

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


config = Config()
