from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from .. import auth
from ..config import config

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict:
    ok_user = hmac.compare_digest(body.username, config.admin_user)
    ok_pass = auth.verify_password(body.password)
    if not (ok_user and ok_pass):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    auth.create_session(response)
    return {"user": config.admin_user}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    auth.destroy_session(request, response)
    return {"ok": True}


@router.get("/me")
def me(user: str = Depends(auth.current_user)) -> dict:
    return {"user": user}
