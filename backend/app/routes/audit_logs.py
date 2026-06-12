from __future__ import annotations

from io import StringIO, BytesIO
import csv
import json
import zipfile

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.audit_integrity import verify_audit_chain
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
        "previous_hash": row.previous_hash,
        "record_hash": row.record_hash,
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


def _with_chain_status(items: list[dict], verification: dict) -> list[dict]:
    return [
        {
            **item,
            "chain_valid": verification["valid"],
            "chain_records_verified": verification["records_verified"],
            "chain_corruption_detected": not verification["valid"],
        }
        for item in items
    ]


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    rows = _tenant_rows(db, tenant["tenant_id"], limit)
    return {"items": [_response(r) for r in rows]}


@router.get("/audit/integrity")
def audit_integrity(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    verification = verify_audit_chain(db, tenant["tenant_id"])
    return {
        "chain_status": "valid" if verification["valid"] else "invalid",
        "valid": verification["valid"],
        "records_verified": verification["records_verified"],
        "corruption_detected": not verification["valid"],
        "first_corrupted_record": verification["first_corrupted_record"],
    }


@router.get("/audit-logs/export.json")
def export_audit_logs_json(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    rows = _tenant_rows(db, tenant["tenant_id"], 5000)
    return JSONResponse(
        {
            "items": [_response(r) for r in rows],
            "chain_verification": verify_audit_chain(db, tenant["tenant_id"]),
        }
    )


@router.get("/audit-logs/export.csv")
def export_audit_logs_csv(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_tenant_roles("tenant_admin", "site_admin")),
):
    items = [_response(r) for r in _tenant_rows(db, tenant["tenant_id"], 5000)]
    verification = verify_audit_chain(db, tenant["tenant_id"])
    items = _with_chain_status(items, verification)
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
    verification = verify_audit_chain(db, tenant["tenant_id"])
    items = _with_chain_status(items, verification)
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
    chain_verification = verify_audit_chain(db, tenant["tenant_id"])
    tabular_items = _with_chain_status(items, chain_verification)

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"lumenai_{tenant['tenant_id']}_audit_logs.json",
            json.dumps({"items": items, "chain_verification": chain_verification}, indent=2),
        )
        zf.writestr(f"lumenai_{tenant['tenant_id']}_audit_logs.csv", _csv_text(tabular_items))
        zf.writestr(f"lumenai_{tenant['tenant_id']}_audit_logs.xlsx", _xlsx_bytes(tabular_items))
        zf.writestr(
            f"lumenai_{tenant['tenant_id']}_audit_integrity.json",
            json.dumps(chain_verification, indent=2),
        )
    bio.seek(0)

    return StreamingResponse(
        bio,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=lumenai_{tenant['tenant_id']}_audit_logs_bundle.zip"},
    )
