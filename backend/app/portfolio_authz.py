from __future__ import annotations

from fastapi import Depends, HTTPException

from app.auth import get_current_user


GLOBAL_PORTFOLIO_ROLES = {"platform_admin", "portfolio_admin", "tenant_admin"}


def require_portfolio_access(
    current_user=Depends(get_current_user),
):
    user_email = (current_user or {}).get("user_email", "") or ""
    role_name = (current_user or {}).get("role_name", "") or ""

    allowed = False

    if role_name in GLOBAL_PORTFOLIO_ROLES:
        allowed = True

    if user_email in {"admin@local", "portfolio@local", "platform@local"}:
        allowed = True

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"User '{user_email or 'unknown'}' is not authorized for portfolio access.",
        )

    return {
        "user_email": user_email,
        "role_name": role_name or "portfolio_admin",
        "portfolio_scope": "global",
    }
