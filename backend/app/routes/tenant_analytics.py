from __future__ import annotations

from collections import defaultdict
from io import StringIO, BytesIO
from typing import Any
import csv
import json
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.authz import require_roles
from app.deps import get_db
from app.db import models
from app.tenant import resolve_tenant

router = APIRouter(tags=["tenant-analytics"])

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


def _require_tenant_access(db: Session, current_user: Any, tenant_id: str) -> None:
    if not _has_tenant_access(db, current_user, tenant_id):
        raise HTTPException(status_code=403, detail="Tenant analytics is outside tenant scope")


def _tenant_rows(db: Session, tenant_id: str):
    return (
        db.query(models.Inspection)
        .filter(models.Inspection.tenant_id == tenant_id)
        .order_by(models.Inspection.id.desc())
        .all()
    )


def _build_summary(rows: list[models.Inspection], tenant_id: str, tenant_name: str):
    total = len(rows)
    completed = sum(1 for r in rows if (r.status or "").lower() == "completed")
    open_alerts = sum(1 for r in rows if (getattr(r, "alert_status", "open") or "").lower() != "resolved")
    resolved_alerts = sum(1 for r in rows if (getattr(r, "alert_status", "") or "").lower() == "resolved")
    high_risk_count = sum(1 for r in rows if int(getattr(r, "risk_score", 0) or 0) >= 80)

    site_counter: dict[str, int] = defaultdict(int)
    vendor_counter: dict[str, int] = defaultdict(int)

    for r in rows:
        site_counter[(getattr(r, "site_name", None) or "default-site").strip() or "default-site"] += 1
        vendor_counter[(getattr(r, "vendor_name", None) or "unknown").strip() or "unknown"] += 1

    def top_items(d: dict[str, int], limit: int = 10):
        return sorted(
            [{"label": k, "count": v} for k, v in d.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:limit]

    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "total_inspections": total,
        "completed": completed,
        "completion_rate": round(completed / total, 4) if total else 0.0,
        "open_alerts": open_alerts,
        "resolved_alerts": resolved_alerts,
        "high_risk_count": high_risk_count,
        "top_sites": top_items(site_counter),
        "top_vendors": top_items(vendor_counter),
    }


def _csv_text(rows: list[models.Inspection]) -> str:
    output = StringIO()
    items = []
    for r in rows:
        items.append({
            "inspection_id": r.id,
            "tenant_id": r.tenant_id,
            "tenant_name": r.tenant_name,
            "site_name": r.site_name,
            "vendor_name": r.vendor_name,
            "file_name": r.file_name,
            "status": r.status,
            "risk_score": r.risk_score,
            "detected_issue": r.detected_issue,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    if items:
        writer = csv.DictWriter(output, fieldnames=list(items[0].keys()))
        writer.writeheader()
        writer.writerows(items)

    return output.getvalue()


def _xlsx_bytes(summary: dict, rows: list[models.Inspection]) -> bytes:
    wb = Workbook()

    ws = wb.active
    ws.title = "Tenant Summary"
    ws.append(["metric", "value"])
    for k, v in summary.items():
        if isinstance(v, list):
            ws.append([k, json.dumps(v)])
        else:
            ws.append([k, v])

    ws2 = wb.create_sheet("Inspections")
    headers = ["inspection_id", "tenant_id", "tenant_name", "site_name", "vendor_name", "file_name", "status", "risk_score", "detected_issue", "created_at"]
    ws2.append(headers)
    for r in rows:
        ws2.append([
            r.id,
            r.tenant_id,
            r.tenant_name,
            r.site_name,
            r.vendor_name,
            r.file_name,
            r.status,
            r.risk_score,
            r.detected_issue,
            r.created_at.isoformat() if r.created_at else None,
        ])

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


@router.get("/tenant-analytics/summary")
def tenant_analytics_summary(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    _require_tenant_access(db, current_user, tenant["tenant_id"])
    rows = _tenant_rows(db, tenant["tenant_id"])
    summary = _build_summary(rows, tenant["tenant_id"], tenant["tenant_name"])
    return JSONResponse(summary)


@router.get("/tenant-analytics/export.json")
def tenant_analytics_export_json(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    _require_tenant_access(db, current_user, tenant["tenant_id"])
    rows = _tenant_rows(db, tenant["tenant_id"])
    summary = _build_summary(rows, tenant["tenant_id"], tenant["tenant_name"])
    payload = {
        "summary": summary,
        "items": [
            {
                "inspection_id": r.id,
                "tenant_id": r.tenant_id,
                "tenant_name": r.tenant_name,
                "site_name": r.site_name,
                "vendor_name": r.vendor_name,
                "file_name": r.file_name,
                "status": r.status,
                "risk_score": r.risk_score,
                "detected_issue": r.detected_issue,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
    return JSONResponse(payload)


@router.get("/tenant-analytics/export.csv")
def tenant_analytics_export_csv(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    _require_tenant_access(db, current_user, tenant["tenant_id"])
    rows = _tenant_rows(db, tenant["tenant_id"])
    return StreamingResponse(
        iter([_csv_text(rows)]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lumenai_{tenant['tenant_id']}_analytics.csv"},
    )


@router.get("/tenant-analytics/export.xlsx")
def tenant_analytics_export_xlsx(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    _require_tenant_access(db, current_user, tenant["tenant_id"])
    rows = _tenant_rows(db, tenant["tenant_id"])
    summary = _build_summary(rows, tenant["tenant_id"], tenant["tenant_name"])
    content = _xlsx_bytes(summary, rows)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=lumenai_{tenant['tenant_id']}_analytics.xlsx"},
    )


@router.get("/tenant-analytics/export.bundle.zip")
def tenant_analytics_export_bundle(
    tenant: dict = Depends(resolve_tenant),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    _require_tenant_access(db, current_user, tenant["tenant_id"])
    rows = _tenant_rows(db, tenant["tenant_id"])
    summary = _build_summary(rows, tenant["tenant_id"], tenant["tenant_name"])
    payload = {
        "summary": summary,
        "items": [
            {
                "inspection_id": r.id,
                "tenant_id": r.tenant_id,
                "tenant_name": r.tenant_name,
                "site_name": r.site_name,
                "vendor_name": r.vendor_name,
                "file_name": r.file_name,
                "status": r.status,
                "risk_score": r.risk_score,
                "detected_issue": r.detected_issue,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"lumenai_{tenant['tenant_id']}_analytics.json", json.dumps(payload, indent=2))
        zf.writestr(f"lumenai_{tenant['tenant_id']}_analytics.csv", _csv_text(rows))
        zf.writestr(f"lumenai_{tenant['tenant_id']}_analytics.xlsx", _xlsx_bytes(summary, rows))
    bio.seek(0)

    return StreamingResponse(
        bio,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=lumenai_{tenant['tenant_id']}_analytics_bundle.zip"},
    )
