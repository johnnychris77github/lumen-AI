from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.db import models
from app.agent.spd_agent import build_agent_assessment

router = APIRouter(tags=["agent"])

GLOBAL_ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


def _user_value(current_user: Any, key: str) -> Any:
    if isinstance(current_user, dict):
        return current_user.get(key)
    return getattr(current_user, key, None)


def _user_email(current_user: Any) -> str:
    return str(
        _user_value(current_user, "email")
        or _user_value(current_user, "user_email")
        or _user_value(current_user, "username")
        or ""
    ).strip().lower()


def _is_global_admin(current_user: Any) -> bool:
    return str(_user_value(current_user, "role") or _user_value(current_user, "role_name") or "") in GLOBAL_ADMIN_ROLES


def _has_tenant_access(db: Session, current_user: Any, tenant_id: str) -> bool:
    if _is_global_admin(current_user):
        return True

    email = _user_email(current_user)
    if not email:
        return False

    return (
        db.query(models.TenantMembership)
        .filter(
            models.TenantMembership.user_email == email,
            models.TenantMembership.tenant_id == tenant_id,
            models.TenantMembership.is_enabled.is_(True),
        )
        .first()
        is not None
    )


def _scoped_inspection_query(db: Session, current_user: Any):
    q = db.query(models.Inspection)
    if _is_global_admin(current_user):
        return q

    email = _user_email(current_user)
    return (
        q.join(
            models.TenantMembership,
            models.TenantMembership.tenant_id == models.Inspection.tenant_id,
        )
        .filter(
            models.TenantMembership.user_email == email,
            models.TenantMembership.is_enabled.is_(True),
        )
    )


@router.get("/agent/inspection/{inspection_id}")
def get_agent_assessment(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    row = (
        db.query(models.Inspection)
        .filter(models.Inspection.id == inspection_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if not _has_tenant_access(db, current_user, row.tenant_id):
        raise HTTPException(status_code=403, detail="Inspection is outside tenant scope")

    return build_agent_assessment(row)


@router.get("/agent/feed")
def get_agent_feed(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = (
        _scoped_inspection_query(db, current_user)
        .order_by(models.Inspection.id.desc())
        .limit(limit)
        .all()
    )
    return {"items": [build_agent_assessment(r) for r in rows]}
