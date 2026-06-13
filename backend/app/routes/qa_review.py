from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.authz import require_roles
from app.deps import get_db
from app.db import models

router = APIRouter(tags=["qa-review"])

GLOBAL_ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


class QAReviewPayload(BaseModel):
    reviewer: str = ""
    notes: str = ""
    approve_model: bool = True
    override_stain_detected: bool | None = None
    override_material_type: str = ""
    override_instrument_type: str = ""
    override_detected_issue: str = ""
    override_risk_score: int | None = None


def inspection_response(row: models.Inspection) -> dict:
    return {
        "id": row.id,
        "file_name": row.file_name,
        "vendor_name": row.vendor_name,
        "status": row.status,
        "stain_detected": row.stain_detected,
        "confidence": row.confidence,
        "material_type": row.material_type,
        "instrument_type": row.instrument_type,
        "detected_issue": row.detected_issue,
        "risk_score": row.risk_score,
        "qa_review_status": row.qa_review_status,
        "qa_reviewer": row.qa_reviewer,
        "qa_review_notes": row.qa_review_notes,
        "qa_reviewed_at": row.qa_reviewed_at.isoformat() if row.qa_reviewed_at else None,
        "qa_override_stain_detected": row.qa_override_stain_detected,
        "qa_override_material_type": row.qa_override_material_type,
        "qa_override_instrument_type": row.qa_override_instrument_type,
        "qa_override_detected_issue": row.qa_override_detected_issue,
        "qa_override_risk_score": row.qa_override_risk_score,
    }


def _user_value(current_user: Any, key: str) -> Any:
    if isinstance(current_user, dict):
        return current_user.get(key)
    return getattr(current_user, key, None)


def _user_email(current_user: Any) -> str:
    return str(_user_value(current_user, "email") or _user_value(current_user, "user_email") or _user_value(current_user, "username") or "").strip().lower()


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
        q.join(models.TenantMembership, models.TenantMembership.tenant_id == models.Inspection.tenant_id)
        .filter(models.TenantMembership.user_email == email, models.TenantMembership.is_enabled.is_(True))
    )


@router.get("/qa-review/pending")
def get_pending_reviews(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = (
        _scoped_inspection_query(db, current_user)
        .filter(models.Inspection.qa_review_status == "pending")
        .order_by(models.Inspection.id.desc())
        .all()
    )
    return {"items": [inspection_response(r) for r in rows]}


@router.post("/qa-review/{inspection_id}")
def submit_qa_review(
    inspection_id: int,
    payload: QAReviewPayload,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
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

    reviewer = payload.reviewer or getattr(current_user, "email", "unknown")
    row.qa_reviewer = reviewer
    row.qa_review_notes = payload.notes
    row.qa_reviewed_at = datetime.now(timezone.utc)

    if payload.approve_model:
        row.qa_review_status = "approved"
        row.qa_override_stain_detected = None
        row.qa_override_material_type = ""
        row.qa_override_instrument_type = ""
        row.qa_override_detected_issue = ""
        row.qa_override_risk_score = None
    else:
        row.qa_review_status = "overridden"
        row.qa_override_stain_detected = payload.override_stain_detected
        row.qa_override_material_type = payload.override_material_type
        row.qa_override_instrument_type = payload.override_instrument_type
        row.qa_override_detected_issue = payload.override_detected_issue
        row.qa_override_risk_score = payload.override_risk_score

        if payload.override_stain_detected is not None:
            row.stain_detected = payload.override_stain_detected
        if payload.override_material_type:
            row.material_type = payload.override_material_type
        if payload.override_instrument_type:
            row.instrument_type = payload.override_instrument_type
        if payload.override_detected_issue:
            row.detected_issue = payload.override_detected_issue
        if payload.override_risk_score is not None:
            row.risk_score = payload.override_risk_score

    db.add(row)
    db.commit()
    db.refresh(row)

    return {"item": inspection_response(row)}
