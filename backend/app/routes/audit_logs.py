from __future__ import annotations

from io import StringIO, BytesIO
import csv
import json
import zipfile

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.audit_anchor import create_audit_chain_anchor, list_audit_chain_anchors
from app.deps import get_db
from app.db import models
from app.tenant import resolve_tenant
from app.tenant_authz import require_tenant_roles

router = APIRouter(tags=["audit-logs"])


def _response(row: models.AuditLog) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "tenant_name": row.tenant_name,
        "actor_email": row.actor_email,
        "actor_role": row.actor_role,
        "action_type": row.action_type,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "status": row.status,
        "request_method": row.request_method,
        "request_path": row.request_path,
        "client_ip": row.client_ip,
        "details": row.details,
        "compliance_flag": row.compliance_flag,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _anchor_response(row: models.AuditChainAnchor) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "anchor_hash": row.anchor_hash,
        "last_audit_log_id": row.last_audit_log_id,
        "records_covered": row.records_covered,
        "anchor_provider": row.anchor_provider,
        "anchor_reference": row.anchor_reference,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _tenant_rows(db: Session, tenant_id: str, limit: int):
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.tenant_id == tenant_id)
        .order_by(models.AuditLog.id.desc())
        .limit(limit)
        .all()
    )


def _csv_text(items: list[dict]) -> str:
    output = StringIO()
    if items:
        writer = csv.DictWriter(output, fieldnames=list(items[0].keys()))
        writer.writeheader()
        writer.writerows(items)
    return output.getvalue()


def _xlsx_bytes(items: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Audit Logs"

    if items:
        headers = list(items[0].keys())
        ws.append(headers)
        for item in items:
            ws.append([item.get(h, "") for h in headers])

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    rows = _tenant_rows(db, tenant["tenant_id"], limit)
    return {"items": [_response(r) for r in rows]}


@router.post("/audit/integrity/anchor")
def create_audit_anchor(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    anchor = create_audit_chain_anchor(db, tenant["tenant_id"], provider="internal")
    return _anchor_response(anchor)


@router.get("/audit/integrity/anchors")
def audit_anchor_history(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    rows = list_audit_chain_anchors(db, tenant["tenant_id"])
    return {"items": [_anchor_response(row) for row in rows]}


@router.get("/audit-logs/export.json")
def export_audit_logs_json(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    rows = _tenant_rows(db, tenant["tenant_id"], 5000)
    return JSONResponse({"items": [_response(r) for r in rows]})


@router.get("/audit-logs/export.csv")
def export_audit_logs_csv(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    items = [_response(r) for r in _tenant_rows(db, tenant["tenant_id"], 5000)]
    return StreamingResponse(
        iter([_csv_text(items)]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lumenai_{tenant['tenant_id']}_audit_logs.csv"},
    )


@router.get("/audit-logs/export.xlsx")
def export_audit_logs_xlsx(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    items = [_response(r) for r in _tenant_rows(db, tenant["tenant_id"], 5000)]
    return StreamingResponse(
        iter([_xlsx_bytes(items)]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=lumenai_{tenant['tenant_id']}_audit_logs.xlsx"},
    )


@router.get("/audit-logs/export.bundle.zip")
def export_audit_logs_bundle(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    items = [_response(r) for r in _tenant_rows(db, tenant["tenant_id"], 5000)]

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"lumenai_{tenant['tenant_id']}_audit_logs.json", json.dumps({"items": items}, indent=2))
        zf.writestr(f"lumenai_{tenant['tenant_id']}_audit_logs.csv", _csv_text(items))
        zf.writestr(f"lumenai_{tenant['tenant_id']}_audit_logs.xlsx", _xlsx_bytes(items))
    bio.seek(0)

    return StreamingResponse(
        bio,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=lumenai_{tenant['tenant_id']}_audit_logs_bundle.zip"},
    )
