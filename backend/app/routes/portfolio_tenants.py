from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user
from app.db import models
from app.db import session as db_session
from app.portfolio_tenants import (
    create_portfolio_tenant,
    generate_board_briefing_from_portfolio_tenants,
    get_portfolio_tenant,
    list_portfolio_tenants,
    portfolio_tenant_rollup,
    rescore_portfolio_tenants,
    update_portfolio_tenant,
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


router = APIRouter(prefix="/portfolio-tenants", tags=["portfolio-tenants"])

GLOBAL_ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


class PortfolioTenantCreatePayload(BaseModel):
    tenant_name: str
    industry: str = "healthcare"
    go_live_status: str = "not_started"
    renewal_risk: bool = False
    implementation_risk: bool = False
    governance_exception_count: int = 0
    last_qbr_date: str | None = None
    next_qbr_date: str | None = None
    executive_owner: str = ""
    customer_success_owner: str = ""
    notes: str = ""


class PortfolioTenantUpdatePayload(BaseModel):
    tenant_name: str | None = None
    industry: str | None = None
    go_live_status: str | None = None
    renewal_risk: bool | None = None
    implementation_risk: bool | None = None
    governance_exception_count: int | None = None
    last_qbr_date: str | None = None
    next_qbr_date: str | None = None
    executive_owner: str | None = None
    customer_success_owner: str | None = None
    notes: str | None = None


class PortfolioTenantBoardBriefingPayload(BaseModel):
    period_label: str = Field(default="Customer Portfolio Board Review")
    audience: str = Field(default="board")


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
        raise HTTPException(status_code=403, detail="Portfolio tenant is outside tenant scope")


def _require_global_admin(current_user: Any) -> None:
    if not _is_global_admin(current_user):
        raise HTTPException(status_code=403, detail="Global admin role required")


def _filter_tenant_rows(db: Session, current_user: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _is_global_admin(current_user):
        return rows
    allowed = _authorized_tenant_ids(db, current_user)
    return [row for row in rows if str(row.get("id")) in allowed]


def _portfolio_rollup_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    qbr_overdue_count = 0
    governance_exception_total = 0

    from datetime import date

    today = date.today()

    for row in rows:
        status = str(row.get("health_status") or "watch")
        status_counts[status] = status_counts.get(status, 0) + 1
        governance_exception_total += int(row.get("governance_exception_count") or 0)

        next_qbr_date = row.get("next_qbr_date")
        if next_qbr_date:
            try:
                qbr_date = next_qbr_date if isinstance(next_qbr_date, date) else date.fromisoformat(str(next_qbr_date))
                if qbr_date < today:
                    qbr_overdue_count += 1
            except Exception:
                pass

    top_risks = sorted(
        rows,
        key=lambda row: (
            int(row.get("health_score") or 0),
            -int(row.get("governance_exception_count") or 0),
            -int(row.get("id") or 0),
        ),
    )[:5]

    return {
        "tenant_count": len(rows),
        "status_counts": status_counts,
        "healthy_count": status_counts.get("healthy", 0),
        "watch_count": status_counts.get("watch", 0),
        "at_risk_count": status_counts.get("at_risk", 0),
        "critical_count": status_counts.get("critical", 0),
        "qbr_overdue_count": qbr_overdue_count,
        "governance_exception_total": governance_exception_total,
        "top_risks": top_risks,
    }


@router.post("")
def create_tenant(
    payload: PortfolioTenantCreatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_global_admin(current_user)
    return create_portfolio_tenant(db=db, **payload.model_dump())


@router.get("")
def list_tenants(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return _filter_tenant_rows(db, current_user, list_portfolio_tenants(db))


@router.get("/rollup")
def get_tenant_rollup(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not _is_global_admin(current_user):
        return _portfolio_rollup_from_rows(_filter_tenant_rows(db, current_user, list_portfolio_tenants(db, limit=10000)))
    return portfolio_tenant_rollup(db)


@router.post("/rescore")
def rescore_tenants(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_global_admin(current_user)
    return rescore_portfolio_tenants(db)


@router.post("/generate-board-briefing")
def generate_tenant_board_briefing(
    payload: PortfolioTenantBoardBriefingPayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    _require_global_admin(current_user)
    return generate_board_briefing_from_portfolio_tenants(
        db=db,
        period_label=payload.period_label,
        audience=payload.audience,
    )


@router.get("/{tenant_id}")
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    tenant = get_portfolio_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Portfolio tenant not found")
    _require_tenant_access(db, current_user, tenant_id)

    return tenant


@router.patch("/{tenant_id}")
def update_tenant(
    tenant_id: int,
    payload: PortfolioTenantUpdatePayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    tenant = get_portfolio_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Portfolio tenant not found")
    _require_tenant_access(db, current_user, tenant_id)

    updates: dict[str, Any] = {
        key: value
        for key, value in payload.model_dump().items()
        if value is not None
    }

    tenant = update_portfolio_tenant(db, tenant_id, updates)
    if not tenant:
        raise HTTPException(status_code=404, detail="Portfolio tenant not found")

    return tenant
