from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.db import models
from app.db import session as db_session
from app.tenant_insights import (
    get_tenant_insight,
    get_top_risk_tenant_insights,
    portfolio_insight_rollup,
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


router = APIRouter(prefix="/tenant-insights", tags=["tenant-insights"])

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
        raise HTTPException(status_code=403, detail="Tenant insight is outside tenant scope")


def _filter_insights(db: Session, current_user: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _is_global_admin(current_user):
        return rows
    allowed = _authorized_tenant_ids(db, current_user)
    return [row for row in rows if str(row.get("tenant_id")) in allowed]


def _insight_rollup_from_rows(insights: list[dict[str, Any]]) -> dict[str, Any]:
    board_attention = [item for item in insights if item["board_attention_required"]]
    critical = [item for item in insights if item["health_status"] == "critical"]
    high_or_moderate = [item for item in insights if item["risk_level"] in {"high", "moderate"}]

    return {
        "tenant_insight_count": len(insights),
        "board_attention_count": len(board_attention),
        "critical_count": len(critical),
        "high_or_moderate_count": len(high_or_moderate),
        "top_board_attention_items": board_attention[:5],
        "executive_focus_summary": (
            f"{len(board_attention)} tenant(s) require executive attention. "
            f"{len(critical)} tenant(s) are critical. "
            f"{len(high_or_moderate)} tenant(s) are high or moderate risk."
        ),
    }


@router.get("/top-risks")
def top_risk_insights(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not _is_global_admin(current_user):
        return _filter_insights(db, current_user, get_top_risk_tenant_insights(db, limit=1000))[:10]
    return get_top_risk_tenant_insights(db)


@router.get("/rollup")
def tenant_insight_rollup(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not _is_global_admin(current_user):
        return _insight_rollup_from_rows(_filter_insights(db, current_user, get_top_risk_tenant_insights(db, limit=1000)))
    return portfolio_insight_rollup(db)


@router.get("/{tenant_id}")
def tenant_insight(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    insight = get_tenant_insight(db, tenant_id)
    if not insight:
        raise HTTPException(status_code=404, detail="Tenant insight not found")
    _require_tenant_access(db, current_user, tenant_id)

    return insight
