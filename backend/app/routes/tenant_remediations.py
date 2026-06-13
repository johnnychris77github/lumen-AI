from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.db import models
from app.db import session as db_session
from app.tenant_remediations import (
    create_remediations_from_tenant_insight,
    create_tenant_remediation,
    get_tenant_remediation,
    list_tenant_remediations,
    remediation_rollup,
    update_tenant_remediation,
)


def get_db():
    if hasattr(db_session, "get_db"):
        yield from db_session.get_db()
        return

    if hasattr(db_session, "get_session"):
        yield from db_session.get_session()
        return

    if hasattr(db_session, "SessionLocal"):
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()
        return

    raise RuntimeError("No database session provider found in app.db.session")


router = APIRouter(prefix="/tenant-remediations", tags=["tenant-remediations"])

GLOBAL_ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


class TenantRemediationCreatePayload(BaseModel):
    tenant_id: int
    action_title: str
    action_description: str = ""
    owner: str = ""
    due_date: str | None = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal["open", "in_progress", "blocked", "escalated", "closed"] = "open"
    escalation_level: int = Field(default=0, ge=0)
    risk_source: str = "manual"


class TenantRemediationUpdatePayload(BaseModel):
    action_title: str | None = None
    action_description: str | None = None
    owner: str | None = None
    due_date: str | None = None
    priority: Literal["low", "medium", "high", "critical"] | None = None
    status: Literal["open", "in_progress", "blocked", "escalated", "closed"] | None = None
    escalation_level: int | None = None
    risk_source: str | None = None


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


def _user_role(current_user: Any) -> str:
    return str(
        _user_value(current_user, "role")
        or _user_value(current_user, "role_name")
        or ""
    )


def _is_global_admin(current_user: Any) -> bool:
    return _user_role(current_user) in GLOBAL_ADMIN_ROLES


def _authorized_tenant_ids(db: Session, current_user: Any) -> set[str]:
    if _is_global_admin(current_user):
        return set()

    email = _user_email(current_user)
    if not email:
        return set()

    rows = (
        db.query(models.TenantMembership)
        .filter(
            models.TenantMembership.user_email == email,
            models.TenantMembership.is_enabled.is_(True),
        )
        .all()
    )
    return {str(row.tenant_id) for row in rows}


def _has_tenant_access(db: Session, current_user: Any, tenant_id: int | str) -> bool:
    if _is_global_admin(current_user):
        return True

    email = _user_email(current_user)
    if not email:
        return False

    return (
        db.query(models.TenantMembership)
        .filter(
            models.TenantMembership.user_email == email,
            models.TenantMembership.tenant_id == str(tenant_id),
            models.TenantMembership.is_enabled.is_(True),
        )
        .first()
        is not None
    )


def _require_tenant_access(db: Session, current_user: Any, tenant_id: int | str) -> None:
    if not _has_tenant_access(db, current_user, tenant_id):
        raise HTTPException(status_code=403, detail="Tenant remediation is outside tenant scope")


def _filter_remediation_rows(db: Session, current_user: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _is_global_admin(current_user):
        return rows
    allowed = _authorized_tenant_ids(db, current_user)
    return [row for row in rows if str(row.get("tenant_id")) in allowed]


def _remediation_rollup_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def count_status(status: str) -> int:
        return sum(1 for row in rows if row.get("status") == status)

    from datetime import date

    today = date.today()
    overdue = 0
    for row in rows:
        due_date = row.get("due_date")
        if not due_date or row.get("status") == "closed":
            continue
        try:
            parsed = due_date if isinstance(due_date, date) else date.fromisoformat(str(due_date))
            if parsed < today:
                overdue += 1
        except Exception:
            pass

    return {
        "total": len(rows),
        "open": count_status("open"),
        "in_progress": count_status("in_progress"),
        "blocked": count_status("blocked"),
        "escalated": count_status("escalated"),
        "closed": count_status("closed"),
        "overdue": overdue,
        "critical_priority": sum(1 for row in rows if row.get("priority") == "critical" and row.get("status") != "closed"),
        "high_priority": sum(1 for row in rows if row.get("priority") == "high" and row.get("status") != "closed"),
    }


@router.post("")
def create_remediation(
    payload: TenantRemediationCreatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_tenant_access(db, current_user, payload.tenant_id)

    try:
        return create_tenant_remediation(db=db, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("")
def list_remediations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return _filter_remediation_rows(db, current_user, list_tenant_remediations(db, limit=10000))


@router.get("/rollup")
def get_remediation_rollup(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not _is_global_admin(current_user):
        return _remediation_rollup_from_rows(_filter_remediation_rows(db, current_user, list_tenant_remediations(db, limit=10000)))
    return remediation_rollup(db)


@router.get("/open")
def list_open_remediations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return _filter_remediation_rows(db, current_user, list_tenant_remediations(db, status="open", limit=10000))


@router.get("/overdue")
def list_overdue_remediations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return _filter_remediation_rows(db, current_user, list_tenant_remediations(db, overdue_only=True, limit=10000))


@router.post("/from-insight/{tenant_id}")
def create_from_insight(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_tenant_access(db, current_user, tenant_id)

    try:
        return create_remediations_from_tenant_insight(db, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{remediation_id}")
def get_remediation(
    remediation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    remediation = get_tenant_remediation(db, remediation_id)
    if not remediation:
        raise HTTPException(status_code=404, detail="Tenant remediation not found")
    _require_tenant_access(db, current_user, remediation["tenant_id"])

    return remediation


@router.patch("/{remediation_id}")
def update_remediation(
    remediation_id: int,
    payload: TenantRemediationUpdatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    remediation = get_tenant_remediation(db, remediation_id)
    if not remediation:
        raise HTTPException(status_code=404, detail="Tenant remediation not found")
    _require_tenant_access(db, current_user, remediation["tenant_id"])

    updates: dict[str, Any] = {
        key: value
        for key, value in payload.model_dump().items()
        if value is not None
    }

    remediation = update_tenant_remediation(db, remediation_id, updates)
    if not remediation:
        raise HTTPException(status_code=404, detail="Tenant remediation not found")

    return remediation


@router.post("/{remediation_id}/close")
def close_remediation(
    remediation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    remediation = get_tenant_remediation(db, remediation_id)
    if not remediation:
        raise HTTPException(status_code=404, detail="Tenant remediation not found")
    _require_tenant_access(db, current_user, remediation["tenant_id"])

    remediation = update_tenant_remediation(db, remediation_id, {"status": "closed"})
    if not remediation:
        raise HTTPException(status_code=404, detail="Tenant remediation not found")

    return remediation
