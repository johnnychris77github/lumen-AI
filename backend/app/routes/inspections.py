from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.db import models

router = APIRouter(tags=["inspections"])

ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


def _user_value(current_user: Any, key: str) -> Any:
    if isinstance(current_user, dict):
        return current_user.get(key)
    return getattr(current_user, key, None)


def inspection_response(row: models.Inspection) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "file_name": row.file_name,
        "tenant_id": row.tenant_id,
        "tenant_name": row.tenant_name,
        "stain_detected": row.stain_detected,
        "confidence": row.confidence,
        "material_type": row.material_type,
        "status": row.status,
        "model_name": row.model_name,
        "model_version": row.model_version,
        "inference_timestamp": row.inference_timestamp.isoformat() if row.inference_timestamp else None,
        "instrument_type": row.instrument_type,
        "detected_issue": row.detected_issue,
        "inference_mode": row.inference_mode,
        "risk_score": row.risk_score,
        "vendor_name": row.vendor_name,
        "site_name": row.site_name,
    }


def _can_read_inspection(row: models.Inspection, current_user: Any) -> bool:
    role = _user_value(current_user, "role")
    if role in ADMIN_ROLES:
        return True
    return row.tenant_id == _user_value(current_user, "tenant_id")


@router.get("/inspections/{inspection_id}")
def get_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    row = (
        db.query(models.Inspection)
        .filter(models.Inspection.id == inspection_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection not found",
        )

    if not _can_read_inspection(row, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return inspection_response(row)
