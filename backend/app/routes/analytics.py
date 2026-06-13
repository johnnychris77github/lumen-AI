from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.deps import get_current_user, get_db
from app.db import models

router = APIRouter(tags=["analytics"])


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


@router.get("/analytics/powerbi")
def powerbi_dataset(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    rows = _scoped_inspection_query(db, current_user).all()

    dataset = []

    for r in rows:
        dataset.append({
            "inspection_id": r.id,
            "instrument_type": r.instrument_type,
            "detected_issue": r.detected_issue,
            "material_type": r.material_type,
            "confidence": r.confidence,
            "status": r.status,
            "timestamp": r.created_at
        })

    return dataset
