from __future__ import annotations

from fastapi import Header, HTTPException

from app.core.session_security import validate_api_token
from app.core.settings import settings


def get_current_user(authorization: str | None = Header(default=None, alias="Authorization")) -> dict:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    actor = validate_api_token(token, settings)
    if actor.token_type in {"dev_token", "api_token", "jwt"}:
        return {
            "user_email": actor.email,
            "role_name": "platform_admin" if actor.role == "admin" else actor.role,
        }

    raise HTTPException(status_code=401, detail="Unauthorized")
