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

router = APIRouter(tags=["site-analytics"])


GLOBAL_ADMIN_ROLES = {"admin", "super_admin", "security_admin"}


def _user_value(current_user: Any, key: str) -> Any:
    if isinstance(current_user, dict):
        return current_user.get(key)
    return getattr(current_user, key, None)


def _user_email(current_user: Any) -> str:
    return str(_user_value(current_user, "email") or _user_value(current_user, "user_email") or _user_value(current_user, "username") or "").strip().lower()


def _is_global_admin(current_user: Any) -> bool:
    return str(_user_value(current_user, "role") or _user_value(current_user, "role_name") or "") in GLOBAL_ADMIN_ROLES


def _scoped_inspection_rows(db: Session, current_user: Any):
    q = db.query(models.Inspection)
    if _is_global_admin(current_user):
        return q.order_by(models.Inspection.id.desc()).all()
    email = _user_email(current_user)
    return (
        q.join(models.TenantMembership, models.TenantMembership.tenant_id == models.Inspection.tenant_id)
        .filter(models.TenantMembership.user_email == email, models.TenantMembership.is_enabled.is_(True))
        .order_by(models.Inspection.id.desc())
        .all()
    )


def _site_metrics(rows: list[models.Inspection]):
    grouped: dict[str, dict] = defaultdict(lambda: {
        "total_inspections": 0,
        "completed": 0,
        "open_alerts": 0,
        "resolved_alerts": 0,
        "qa_reviewed": 0,
        "qa_overridden": 0,
        "high_risk_count": 0,
        "confidence_total": 0.0,
        "vendors": defaultdict(int),
        "issues": defaultdict(int),
    })

    for r in rows:
        site = (r.site_name or "default-site").strip() or "default-site"
        g = grouped[site]

        g["total_inspections"] += 1
        g["confidence_total"] += float(r.confidence or 0.0)

        if (r.status or "").lower() == "completed":
            g["completed"] += 1
        if (r.alert_status or "").lower() != "resolved":
            g["open_alerts"] += 1
        else:
            g["resolved_alerts"] += 1
        if (r.qa_review_status or "").lower() in {"approved", "overridden"}:
            g["qa_reviewed"] += 1
        if (r.qa_review_status or "").lower() == "overridden":
            g["qa_overridden"] += 1
        if int(r.risk_score or 0) >= 80:
            g["high_risk_count"] += 1

        vendor = (r.vendor_name or "unknown").strip() or "unknown"
        issue = (r.detected_issue or "unknown").strip() or "unknown"
        g["vendors"][vendor] += 1
        g["issues"][issue] += 1

    items = []
    for site, g in grouped.items():
        total = g["total_inspections"] or 1
        qa_reviewed = g["qa_reviewed"] or 1
        top_vendors = sorted(
            [{"label": k, "count": v} for k, v in g["vendors"].items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]
        top_issues = sorted(
            [{"label": k, "count": v} for k, v in g["issues"].items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        items.append({
            "site_name": site,
            "total_inspections": g["total_inspections"],
            "completed": g["completed"],
            "completion_rate": round(g["completed"] / total, 4),
            "open_alerts": g["open_alerts"],
            "resolved_alerts": g["resolved_alerts"],
            "qa_reviewed": g["qa_reviewed"],
            "qa_override_rate": round(g["qa_overridden"] / qa_reviewed, 4) if g["qa_reviewed"] else 0.0,
            "high_risk_count": g["high_risk_count"],
            "avg_confidence": round(g["confidence_total"] / total, 2),
            "top_vendors": top_vendors,
            "top_issues": top_issues,
        })

    items.sort(key=lambda x: (x["open_alerts"], x["qa_override_rate"], x["total_inspections"]), reverse=True)
    return items


def _enterprise_summary(site_items: list[dict]) -> dict:
    total_sites = len(site_items)
    total_inspections = sum(x["total_inspections"] for x in site_items)
    open_alerts = sum(x["open_alerts"] for x in site_items)
    high_risk = sum(x["high_risk_count"] for x in site_items)
    avg_override = round(sum(x["qa_override_rate"] for x in site_items) / total_sites, 4) if total_sites else 0.0

    return {
        "total_sites": total_sites,
        "total_inspections": total_inspections,
        "open_alerts": open_alerts,
        "high_risk_count": high_risk,
        "avg_site_override_rate": avg_override,
    }


def _csv_text(items: list[dict]) -> str:
    output = StringIO()
    if not items:
        return ""
    rows = []
    for item in items:
        rows.append({
            "site_name": item["site_name"],
            "total_inspections": item["total_inspections"],
            "completed": item["completed"],
            "completion_rate": item["completion_rate"],
            "open_alerts": item["open_alerts"],
            "resolved_alerts": item["resolved_alerts"],
            "qa_reviewed": item["qa_reviewed"],
            "qa_override_rate": item["qa_override_rate"],
            "high_risk_count": item["high_risk_count"],
            "avg_confidence": item["avg_confidence"],
            "top_vendor": item["top_vendors"][0]["label"] if item["top_vendors"] else "",
            "top_issue": item["top_issues"][0]["label"] if item["top_issues"] else "",
        })
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _xlsx_bytes(summary: dict, items: list[dict]) -> bytes:
    wb = Workbook()

    ws = wb.active
    ws.title = "Enterprise Summary"
    ws.append(["metric", "value"])
    for k, v in summary.items():
        ws.append([k, v])

    ws2 = wb.create_sheet("Site Benchmarking")
    headers = [
        "site_name", "total_inspections", "completed", "completion_rate",
        "open_alerts", "resolved_alerts", "qa_reviewed", "qa_override_rate",
        "high_risk_count", "avg_confidence", "top_vendor", "top_issue"
    ]
    ws2.append(headers)

    for item in items:
        ws2.append([
            item["site_name"],
            item["total_inspections"],
            item["completed"],
            item["completion_rate"],
            item["open_alerts"],
            item["resolved_alerts"],
            item["qa_reviewed"],
            item["qa_override_rate"],
            item["high_risk_count"],
            item["avg_confidence"],
            item["top_vendors"][0]["label"] if item["top_vendors"] else "",
            item["top_issues"][0]["label"] if item["top_issues"] else "",
        ])

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


@router.get("/site-analytics/summary")
def site_analytics_summary(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _scoped_inspection_rows(db, current_user)
    site_items = _site_metrics(rows)
    summary = _enterprise_summary(site_items)
    return JSONResponse({"enterprise_summary": summary, "sites": site_items})


@router.get("/site-analytics/export.json")
def site_analytics_export_json(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _scoped_inspection_rows(db, current_user)
    site_items = _site_metrics(rows)
    summary = _enterprise_summary(site_items)
    return JSONResponse({"enterprise_summary": summary, "sites": site_items})


@router.get("/site-analytics/export.csv")
def site_analytics_export_csv(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _scoped_inspection_rows(db, current_user)
    site_items = _site_metrics(rows)
    text = _csv_text(site_items)
    return StreamingResponse(
        iter([text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lumenai_site_benchmarking.csv"},
    )


@router.get("/site-analytics/export.xlsx")
def site_analytics_export_xlsx(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _scoped_inspection_rows(db, current_user)
    site_items = _site_metrics(rows)
    summary = _enterprise_summary(site_items)
    content = _xlsx_bytes(summary, site_items)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=lumenai_site_benchmarking.xlsx"},
    )


@router.get("/site-analytics/export.bundle.zip")
def site_analytics_export_bundle(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _scoped_inspection_rows(db, current_user)
    site_items = _site_metrics(rows)
    summary = _enterprise_summary(site_items)

    payload = {"enterprise_summary": summary, "sites": site_items}

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lumenai_site_benchmarking.json", json.dumps(payload, indent=2))
        zf.writestr("lumenai_site_benchmarking.csv", _csv_text(site_items))
        zf.writestr("lumenai_site_benchmarking.xlsx", _xlsx_bytes(summary, site_items))

    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=lumenai_site_benchmarking_bundle.zip"},
    )
