from __future__ import annotations

from collections import defaultdict
from io import StringIO, BytesIO
from typing import Any
import csv
import json
import zipfile

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.authz import require_roles
from app.deps import get_db
from app.db import models

router = APIRouter(tags=["model-performance"])

GLOBAL_ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


def _user_value(current_user: Any, key: str) -> Any:
    if isinstance(current_user, dict):
        return current_user.get(key)
    return getattr(current_user, key, None)


def _user_email(current_user: Any) -> str:
    return str(_user_value(current_user, "email") or _user_value(current_user, "user_email") or _user_value(current_user, "username") or "").strip().lower()


def _is_global_admin(current_user: Any) -> bool:
    return str(_user_value(current_user, "role") or _user_value(current_user, "role_name") or "") in GLOBAL_ADMIN_ROLES


def _reviewed_rows(db: Session, current_user: Any):
    q = db.query(models.Inspection)
    if not _is_global_admin(current_user):
        email = _user_email(current_user)
        q = q.join(models.TenantMembership, models.TenantMembership.tenant_id == models.Inspection.tenant_id).filter(
            models.TenantMembership.user_email == email,
            models.TenantMembership.is_enabled.is_(True),
        )
    return q.filter(models.Inspection.qa_review_status.in_(["approved", "overridden"])).order_by(models.Inspection.id.desc()).all()


def _time_bucket(value):
    if not value:
        return "unknown"
    try:
        return value.date().isoformat()
    except Exception:
        return "unknown"


def _is_override(row: models.Inspection) -> bool:
    return (row.qa_review_status or "").lower() == "overridden"


def _feedback_row(row: models.Inspection) -> dict:
    return {
        "inspection_id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "reviewed_at": row.qa_reviewed_at.isoformat() if row.qa_reviewed_at else None,
        "vendor_name": row.vendor_name,
        "reviewer": row.qa_reviewer or "unknown",
        "issue": row.detected_issue or "unknown",
        "instrument_type": row.instrument_type or "unknown",
        "model_name": row.model_name,
        "model_version": row.model_version,
        "confidence": row.confidence,
        "risk_score": row.risk_score,
        "qa_review_status": row.qa_review_status,
        "override_detected_issue": row.qa_override_detected_issue or "",
        "override_risk_score": row.qa_override_risk_score if row.qa_override_risk_score is not None else "",
    }


def _summary(rows: list[models.Inspection]) -> dict:
    total_reviewed = len(rows)
    overrides = sum(1 for r in rows if _is_override(r))
    approvals = sum(1 for r in rows if (r.qa_review_status or "").lower() == "approved")
    agreement_rate = round((approvals / total_reviewed), 4) if total_reviewed else 0.0
    override_rate = round((overrides / total_reviewed), 4) if total_reviewed else 0.0

    return {
        "total_reviewed": total_reviewed,
        "total_approved": approvals,
        "total_overridden": overrides,
        "agreement_rate": agreement_rate,
        "override_rate": override_rate,
    }


def _group_rate(rows: list[models.Inspection], key_fn):
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"reviewed": 0, "overridden": 0, "approved": 0})
    for r in rows:
        key = key_fn(r) or "unknown"
        grouped[key]["reviewed"] += 1
        if _is_override(r):
            grouped[key]["overridden"] += 1
        elif (r.qa_review_status or "").lower() == "approved":
            grouped[key]["approved"] += 1

    items = []
    for key, stats in grouped.items():
        reviewed = stats["reviewed"]
        overridden = stats["overridden"]
        approved = stats["approved"]
        items.append({
            "label": key,
            "reviewed": reviewed,
            "approved": approved,
            "overridden": overridden,
            "agreement_rate": round((approved / reviewed), 4) if reviewed else 0.0,
            "override_rate": round((overridden / reviewed), 4) if reviewed else 0.0,
        })

    items.sort(key=lambda x: (x["override_rate"], x["reviewed"]), reverse=True)
    return items


def _timeseries(rows: list[models.Inspection]):
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"reviewed": 0, "approved": 0, "overridden": 0})
    for r in rows:
        bucket = _time_bucket(r.qa_reviewed_at or r.created_at)
        grouped[bucket]["reviewed"] += 1
        if _is_override(r):
            grouped[bucket]["overridden"] += 1
        elif (r.qa_review_status or "").lower() == "approved":
            grouped[bucket]["approved"] += 1

    items = []
    for bucket, stats in sorted(grouped.items(), key=lambda kv: kv[0]):
        reviewed = stats["reviewed"]
        approved = stats["approved"]
        overridden = stats["overridden"]
        items.append({
            "date": bucket,
            "reviewed": reviewed,
            "approved": approved,
            "overridden": overridden,
            "agreement_rate": round((approved / reviewed), 4) if reviewed else 0.0,
            "override_rate": round((overridden / reviewed), 4) if reviewed else 0.0,
        })
    return items


def _csv_text(items: list[dict]) -> str:
    output = StringIO()
    if not items:
        return ""
    writer = csv.DictWriter(output, fieldnames=list(items[0].keys()))
    writer.writeheader()
    writer.writerows(items)
    return output.getvalue()


def _xlsx_bytes(summary: dict, by_vendor: list[dict], by_issue: list[dict], by_reviewer: list[dict], timeseries: list[dict], feedback_rows: list[dict]) -> bytes:
    wb = Workbook()

    ws = wb.active
    ws.title = "Summary"
    ws.append(["metric", "value"])
    for k, v in summary.items():
        ws.append([k, v])

    def add_sheet(name: str, items: list[dict]):
        sheet = wb.create_sheet(name)
        if items:
            headers = list(items[0].keys())
            sheet.append(headers)
            for item in items:
                sheet.append([item.get(h, "") for h in headers])

    add_sheet("By Vendor", by_vendor)
    add_sheet("By Issue", by_issue)
    add_sheet("By Reviewer", by_reviewer)
    add_sheet("Timeseries", timeseries)
    add_sheet("Feedback Rows", feedback_rows)

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


@router.get("/model-performance/summary")
def model_performance_summary(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _reviewed_rows(db, current_user)
    summary = _summary(rows)
    by_vendor = _group_rate(rows, lambda r: (r.vendor_name or "unknown").strip() or "unknown")
    by_issue = _group_rate(rows, lambda r: (r.detected_issue or "unknown").strip() or "unknown")
    by_reviewer = _group_rate(rows, lambda r: (r.qa_reviewer or "unknown").strip() or "unknown")
    timeseries = _timeseries(rows)

    return JSONResponse({
        "summary": summary,
        "by_vendor": by_vendor[:20],
        "by_issue": by_issue[:20],
        "by_reviewer": by_reviewer[:20],
        "timeseries": timeseries,
    })


@router.get("/model-performance/export.json")
def model_performance_export_json(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _reviewed_rows(db, current_user)
    summary = _summary(rows)
    by_vendor = _group_rate(rows, lambda r: (r.vendor_name or "unknown").strip() or "unknown")
    by_issue = _group_rate(rows, lambda r: (r.detected_issue or "unknown").strip() or "unknown")
    by_reviewer = _group_rate(rows, lambda r: (r.qa_reviewer or "unknown").strip() or "unknown")
    timeseries = _timeseries(rows)
    feedback_rows = [_feedback_row(r) for r in rows]

    return JSONResponse({
        "summary": summary,
        "by_vendor": by_vendor,
        "by_issue": by_issue,
        "by_reviewer": by_reviewer,
        "timeseries": timeseries,
        "feedback_rows": feedback_rows,
    })


@router.get("/model-performance/export.csv")
def model_performance_export_csv(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _reviewed_rows(db, current_user)
    feedback_rows = [_feedback_row(r) for r in rows]
    text = _csv_text(feedback_rows)
    return StreamingResponse(
        iter([text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lumenai_model_performance_feedback_rows.csv"},
    )


@router.get("/model-performance/export.xlsx")
def model_performance_export_xlsx(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _reviewed_rows(db, current_user)
    summary = _summary(rows)
    by_vendor = _group_rate(rows, lambda r: (r.vendor_name or "unknown").strip() or "unknown")
    by_issue = _group_rate(rows, lambda r: (r.detected_issue or "unknown").strip() or "unknown")
    by_reviewer = _group_rate(rows, lambda r: (r.qa_reviewer or "unknown").strip() or "unknown")
    timeseries = _timeseries(rows)
    feedback_rows = [_feedback_row(r) for r in rows]

    content = _xlsx_bytes(summary, by_vendor, by_issue, by_reviewer, timeseries, feedback_rows)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=lumenai_model_performance.xlsx"},
    )


@router.get("/model-performance/export.bundle.zip")
def model_performance_export_bundle(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _reviewed_rows(db, current_user)
    summary = _summary(rows)
    by_vendor = _group_rate(rows, lambda r: (r.vendor_name or "unknown").strip() or "unknown")
    by_issue = _group_rate(rows, lambda r: (r.detected_issue or "unknown").strip() or "unknown")
    by_reviewer = _group_rate(rows, lambda r: (r.qa_reviewer or "unknown").strip() or "unknown")
    timeseries = _timeseries(rows)
    feedback_rows = [_feedback_row(r) for r in rows]

    payload = {
        "summary": summary,
        "by_vendor": by_vendor,
        "by_issue": by_issue,
        "by_reviewer": by_reviewer,
        "timeseries": timeseries,
        "feedback_rows": feedback_rows,
    }

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lumenai_model_performance.json", json.dumps(payload, indent=2))
        zf.writestr("lumenai_model_performance_feedback_rows.csv", _csv_text(feedback_rows))
        zf.writestr(
            "lumenai_model_performance.xlsx",
            _xlsx_bytes(summary, by_vendor, by_issue, by_reviewer, timeseries, feedback_rows),
        )

    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=lumenai_model_performance_bundle.zip"},
    )
