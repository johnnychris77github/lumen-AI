from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from io import StringIO, BytesIO
import csv
import json
import zipfile

from openpyxl import Workbook

from app.deps import get_db
from app.db import models
from app.authz import require_roles

router = APIRouter(tags=["history"])

ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


def _user_value(current_user, key: str):
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


def build_summary(rows):
    total = len(rows)
    completed = sum(1 for r in rows if (r.status or "").lower() == "completed")
    queued = sum(1 for r in rows if (r.status or "").lower() == "queued")
    running = sum(1 for r in rows if (r.status or "").lower() == "running")
    failed = sum(1 for r in rows if (r.status or "").lower() == "failed")

    issue_counts = {}
    instrument_counts = {}

    for r in rows:
        issue = (r.detected_issue or "unknown").strip() or "unknown"
        instrument = (r.instrument_type or "unknown").strip() or "unknown"
        issue_counts[issue] = issue_counts.get(issue, 0) + 1
        instrument_counts[instrument] = instrument_counts.get(instrument, 0) + 1

    top_issues = sorted(
        [{"label": k, "count": v} for k, v in issue_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    top_instruments = sorted(
        [{"label": k, "count": v} for k, v in instrument_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    return {
        "total_inspections": total,
        "completed": completed,
        "queued": queued,
        "running": running,
        "failed": failed,
        "top_issues": top_issues,
        "top_instruments": top_instruments,
    }


def fetch_rows(db: Session, current_user):
    if _user_value(current_user, "role") in ADMIN_ROLES:
        return db.query(models.Inspection).order_by(models.Inspection.id.desc()).all()

    user_email = _user_value(current_user, "email")
    if not user_email:
        return []

    return (
        db.query(models.Inspection)
        .join(
            models.TenantMembership,
            models.TenantMembership.tenant_id == models.Inspection.tenant_id,
        )
        .filter(
            models.TenantMembership.user_email == user_email,
            models.TenantMembership.is_enabled.is_(True),
        )
        .order_by(models.Inspection.id.desc())
        .all()
    )


def csv_text(rows):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "created_at",
        "file_name",
        "status",
        "stain_detected",
        "confidence",
        "material_type",
        "instrument_type",
        "detected_issue",
        "inference_mode",
        "risk_score",
        "vendor_name",
        "model_name",
        "model_version",
        "inference_timestamp",
    ])
    for r in rows:
        writer.writerow([
            r.id,
            r.created_at.isoformat() if r.created_at else "",
            r.file_name,
            r.status,
            r.stain_detected,
            r.confidence,
            r.material_type,
            r.instrument_type,
            r.detected_issue,
            r.inference_mode,
            r.risk_score,
            r.vendor_name,
            r.model_name,
            r.model_version,
            r.inference_timestamp.isoformat() if r.inference_timestamp else "",
        ])
    return output.getvalue()


def xlsx_bytes(rows):
    wb = Workbook()

    ws = wb.active
    ws.title = "Inspections"
    ws.append([
        "id",
        "created_at",
        "file_name",
        "status",
        "stain_detected",
        "confidence",
        "material_type",
        "instrument_type",
        "detected_issue",
        "inference_mode",
        "risk_score",
        "vendor_name",
        "model_name",
        "model_version",
        "inference_timestamp",
    ])
    for r in rows:
        ws.append([
            r.id,
            r.created_at.isoformat() if r.created_at else "",
            r.file_name,
            r.status,
            r.stain_detected,
            r.confidence,
            r.material_type,
            r.instrument_type,
            r.detected_issue,
            r.inference_mode,
            r.risk_score,
            r.vendor_name,
            r.model_name,
            r.model_version,
            r.inference_timestamp.isoformat() if r.inference_timestamp else "",
        ])

    summary_ws = wb.create_sheet("Summary")
    summary = build_summary(rows)
    summary_ws.append(["metric", "value"])
    for key in ["total_inspections", "completed", "queued", "running", "failed"]:
        summary_ws.append([key, summary[key]])

    summary_ws.append([])
    summary_ws.append(["Top Issues", "count"])
    for item in summary["top_issues"]:
        summary_ws.append([item["label"], item["count"]])

    summary_ws.append([])
    summary_ws.append(["Top Instruments", "count"])
    for item in summary["top_instruments"]:
        summary_ws.append([item["label"], item["count"]])

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


@router.get("/history")
async def get_history(
    limit: int = Query(default=20, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "super_admin", "security_admin", "spd_manager", "vendor_user", "viewer")),
):
    rows = fetch_rows(db, current_user)[:limit]
    return {"items": [inspection_response(r) for r in rows]}


@router.get("/history/summary")
async def get_history_summary(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "super_admin", "security_admin", "spd_manager", "vendor_user", "viewer"))):
    rows = fetch_rows(db, current_user)
    return build_summary(rows)


@router.get("/history/export.json")
async def export_history_json(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "super_admin", "security_admin", "spd_manager", "vendor_user"))):
    rows = fetch_rows(db, current_user)
    return JSONResponse({"items": [inspection_response(r) for r in rows]})


@router.get("/history/export.csv")
async def export_history_csv(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "super_admin", "security_admin", "spd_manager", "vendor_user"))):
    rows = fetch_rows(db, current_user)
    text = csv_text(rows)
    return StreamingResponse(
        iter([text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lumenai_history_export.csv"},
    )


@router.get("/history/export.xlsx")
async def export_history_xlsx(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "super_admin", "security_admin", "spd_manager", "vendor_user"))):
    rows = fetch_rows(db, current_user)
    content = xlsx_bytes(rows)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=lumenai_history_export.xlsx"},
    )


@router.get("/history/export.bundle.zip")
async def export_history_bundle(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "super_admin", "security_admin", "spd_manager", "vendor_user"))):
    rows = fetch_rows(db, current_user)
    summary = build_summary(rows)
    inspections = {"items": [inspection_response(r) for r in rows]}
    csv_content = csv_text(rows)
    xlsx_content = xlsx_bytes(rows)

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lumenai_history_export.csv", csv_content)
        zf.writestr("lumenai_history_export.json", json.dumps(inspections, indent=2))
        zf.writestr("lumenai_summary.json", json.dumps(summary, indent=2))
        zf.writestr("lumenai_history_export.xlsx", xlsx_content)

    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=lumenai_export_bundle.zip"},
    )
