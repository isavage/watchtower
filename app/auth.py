"""Single-admin auth with server-side sessions stored in SQLite.

Login issues a random token stored in an HttpOnly cookie; the token maps to a
sessions row with sliding expiry (refreshed on use) capped by an absolute
max age. Logout deletes the row, invalidating the cookie immediately.
"""
from __future__ import annotations

import hmac
import secrets
import time

from fastapi import Depends, HTTPException, Request, Response, status
from passlib.context import CryptContext
from passlib.hash import bcrypt

from . import store
from .config import config

COOKIE_NAME = "wt_session"
MAX_SESSION_SECONDS = 30 * 24 * 3600  # absolute lifetime: 30 days

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash(password: str) -> str:
    import base64
    import hashlib
    digest = hashlib.sha512(password.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


# Hash the admin password from env once at import; bcrypt caps input at 72
# bytes, so pre-hash with sha512 to support long passphrases safely.
_ADMIN_HASH = bcrypt.using(rounds=12).hash(_prehash(config.admin_password))


def verify_password(password: str) -> bool:
    try:
        return _pwd.verify(_prehash(password), _ADMIN_HASH)
    except (ValueError, TypeError):
        return False


def create_session(response: Response) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    ttl = config.session_days * 24 * 3600
    with store.get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user, created, last_seen, expires) VALUES (?, ?, ?, ?, ?)",
            (token, config.admin_user, now, now, now + ttl),
        )
    _set_cookie(response, token)
    return token


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=config.session_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=config.cookie_secure,
        path="/",
    )


def destroy_session(request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with store.get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    response.delete_cookie(COOKIE_NAME, path="/")


def _lookup(token: str) -> dict | None:
    now = time.time()
    with store.get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
        if not row:
            return None
        if row["expires"] < now or row["created"] + MAX_SESSION_SECONDS < now:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None
        # Sliding expiry, refreshed at most once per minute to cut writes.
        if now - row["last_seen"] > 60:
            new_exp = min(now + config.session_days * 24 * 3600, row["created"] + MAX_SESSION_SECONDS)
            conn.execute("UPDATE sessions SET last_seen = ?, expires = ? WHERE token = ?", (now, new_exp, token))
        return dict(row)


def current_user(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    session = _lookup(token)
    if not session or not hmac.compare_digest(session["user"], config.admin_user):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return session["user"]


AuthRequired = Depends(current_user)
