from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.deps import get_db
from app.db import models
from app.audit import log_audit_event
from app.jobs.inspection_job import run_inspection
from app.metering import record_usage_event, check_quota
from app.event_dispatcher import dispatch_event
from app.tenant import resolve_tenant

router = APIRouter(tags=["inspect"])


def inspection_response(row: models.Inspection) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "file_name": row.file_name,
        "tenant_id": row.tenant_id,
        "tenant_name": row.tenant_name,
        "vendor_name": row.vendor_name,
        "site_name": row.site_name,
        "status": row.status,
    }


@router.post("/stream/frame")
async def stream_frame(
    request: Request,
    frame: UploadFile = File(...),
    vendor_name: str = Form("unknown"),
    site_name: str = Form("default-site"),
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
):
    file_bytes = await frame.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty frame uploaded")

    quota_state = check_quota(db, tenant_id=tenant["tenant_id"], tenant_name=tenant["tenant_name"], metric_key="inspection_submitted")
    if not quota_state["allowed"]:
        raise HTTPException(status_code=429, detail=f'Quota exceeded for inspection_submitted. Used {quota_state["used"]} of {quota_state["limit"]}.')

    row = models.Inspection(
        file_name=frame.filename or "frame.bin",
        tenant_id=tenant["tenant_id"],
        tenant_name=tenant["tenant_name"],
        vendor_name=vendor_name,
        site_name=site_name,
        status="queued",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit_event(
        db,
        tenant_id=tenant["tenant_id"],
        tenant_name=tenant["tenant_name"],
        actor_email="system",
        actor_role="system",
        action_type="inspection_create",
        resource_type="inspection",
        resource_id=row.id,
        request=request,
        details={
            "file_name": row.file_name,
            "vendor_name": row.vendor_name,
            "site_name": row.site_name,
            "status": row.status,
        },
        compliance_flag=True,
    )

    record_usage_event(
        db,
        tenant_id=tenant["tenant_id"],
        tenant_name=tenant["tenant_name"],
        event_type="inspection_submitted",
        quantity=1,
        resource_id=row.id,
        notes=row.file_name,
    )

    run_inspection(row.id, file_bytes)

    dispatch_event(
        db,
        tenant_id=tenant["tenant_id"],
        tenant_name=tenant["tenant_name"],
        trigger_type="inspection_submitted",
        payload={
            "inspection_id": row.id,
            "file_name": row.file_name,
            "vendor_name": row.vendor_name,
            "site_name": row.site_name,
            "status": row.status,
        },
    )

    return {
        "status": "queued",
        "inspection": inspection_response(row),
    }
