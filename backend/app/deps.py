from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import log_audit_event
from app.core.session_security import get_authenticated_actor
from app.core.settings import settings
from app.db import SessionLocal
from app.db import models


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        actor = get_authenticated_actor(request, settings)
    except HTTPException as exc:
        try:
            log_audit_event(
                db,
                tenant_id=request.headers.get("x-tenant-id") or "default-tenant",
                tenant_name=request.headers.get("x-tenant-name") or "Default Tenant",
                actor_email="anonymous",
                actor_role="anonymous",
                action_type="authentication_failed",
                resource_type="api_request",
                resource_id=f"{request.method} {request.url.path}",
                status="failed",
                request=request,
                details={"reason": exc.detail},
                compliance_flag=True,
            )
        except Exception:
            pass
        raise

    if actor.token_type in {"dev_token", "configured_api_token"}:
        return actor

    if actor.token_type == "user_email":
        user = (
            db.query(models.User)
            .filter(models.User.email == actor.email)
            .first()
        )
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
    )
