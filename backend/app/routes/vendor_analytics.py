from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from io import StringIO, BytesIO
import csv
import json
import zipfile

from openpyxl import Workbook

from app.deps import get_db
from app.db import models
from app.reports.vendor_scorecard import generate_vendor_scorecard_pdf
from app.authz import require_roles

router = APIRouter(tags=["vendor-analytics"])

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


def _scoped_inspection_query(db: Session, current_user: Any):
    q = db.query(models.Inspection)
    if _is_global_admin(current_user):
        return q

    email = _user_email(current_user)
    return (
        q.join(
            models.TenantMembership,
            models.TenantMembership.tenant_id == models.Inspection.tenant_id,
        )
        .filter(
            models.TenantMembership.user_email == email,
            models.TenantMembership.is_enabled.is_(True),
        )
    )


def _scoped_inspection_rows(db: Session, current_user: Any):
    return _scoped_inspection_query(db, current_user).all()


def build_vendor_items(rows):
    vendor_summary = {}

    for r in rows:
        vendor = (r.vendor_name or "unknown").strip() or "unknown"
        if vendor not in vendor_summary:
            vendor_summary[vendor] = {
                "vendor_name": vendor,
                "total_inspections": 0,
                "escalations": 0,
                "avg_confidence_total": 0.0,
                "top_issues": {},
                "high_risk_count": 0,
                "latest_issue": "unknown",
            }

        vendor_summary[vendor]["total_inspections"] += 1
        vendor_summary[vendor]["avg_confidence_total"] += float(r.confidence or 0.0)

        issue = (r.detected_issue or "unknown").strip() or "unknown"
        vendor_summary[vendor]["latest_issue"] = issue
        vendor_summary[vendor]["top_issues"][issue] = vendor_summary[vendor]["top_issues"].get(issue, 0) + 1

        risk_score = int(r.risk_score or 0)
        if risk_score >= 50 or issue.lower() in {"debris", "stain", "corrosion"}:
            vendor_summary[vendor]["escalations"] += 1
        if risk_score >= 80:
            vendor_summary[vendor]["high_risk_count"] += 1

    items = []
    for vendor, stats in vendor_summary.items():
        total = stats["total_inspections"] or 1
        avg_confidence = round(stats["avg_confidence_total"] / total, 2)
        top_issues = sorted(
            [{"label": k, "count": v} for k, v in stats["top_issues"].items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        items.append({
            "vendor_name": vendor,
            "total_inspections": stats["total_inspections"],
            "escalations": stats["escalations"],
            "high_risk_count": stats["high_risk_count"],
            "avg_confidence": avg_confidence,
            "top_issues": top_issues,
            "latest_issue": stats["latest_issue"],
        })

    items.sort(key=lambda x: (x["escalations"], x["high_risk_count"], x["total_inspections"]), reverse=True)
    return items


def find_vendor_scorecard(items, vendor_name: str):
    for item in items:
        if item["vendor_name"].strip().lower() == vendor_name.strip().lower():
            return item
    return None


def vendor_csv_text(items):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "vendor_name",
        "total_inspections",
        "escalations",
        "high_risk_count",
        "avg_confidence",
        "top_issue",
        "top_issue_count",
        "latest_issue",
    ])

    for item in items:
        top_issue = item["top_issues"][0]["label"] if item["top_issues"] else "unknown"
        top_issue_count = item["top_issues"][0]["count"] if item["top_issues"] else 0
        writer.writerow([
            item["vendor_name"],
            item["total_inspections"],
            item["escalations"],
            item["high_risk_count"],
            item["avg_confidence"],
            top_issue,
            top_issue_count,
            item["latest_issue"],
        ])

    return output.getvalue()


def vendor_xlsx_bytes(items):
    wb = Workbook()

    ws = wb.active
    ws.title = "Vendor Scorecards"
    ws.append([
        "vendor_name",
        "total_inspections",
        "escalations",
        "high_risk_count",
        "avg_confidence",
        "top_issue",
        "top_issue_count",
        "latest_issue",
    ])

    for item in items:
        top_issue = item["top_issues"][0]["label"] if item["top_issues"] else "unknown"
        top_issue_count = item["top_issues"][0]["count"] if item["top_issues"] else 0
        ws.append([
            item["vendor_name"],
            item["total_inspections"],
            item["escalations"],
            item["high_risk_count"],
            item["avg_confidence"],
            top_issue,
            top_issue_count,
            item["latest_issue"],
        ])

    detail_ws = wb.create_sheet("Top Issues Detail")
    detail_ws.append(["vendor_name", "issue", "count"])
    for item in items:
        if not item["top_issues"]:
            detail_ws.append([item["vendor_name"], "unknown", 0])
        else:
            for issue in item["top_issues"]:
                detail_ws.append([item["vendor_name"], issue["label"], issue["count"]])

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.getvalue()


@router.get("/analytics/vendors")
def vendor_analytics(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "spd_manager", "vendor_user", "viewer"))):
    rows = _scoped_inspection_rows(db, current_user)
    return {"items": build_vendor_items(rows)}


@router.get("/analytics/vendors/export.json")
def vendor_analytics_export_json(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "spd_manager", "vendor_user"))):
    rows = _scoped_inspection_rows(db, current_user)
    items = build_vendor_items(rows)
    return JSONResponse({"items": items})


@router.get("/analytics/vendors/export.csv")
def vendor_analytics_export_csv(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "spd_manager", "vendor_user"))):
    rows = _scoped_inspection_rows(db, current_user)
    items = build_vendor_items(rows)
    text = vendor_csv_text(items)
    return StreamingResponse(
        iter([text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lumenai_vendor_scorecards.csv"},
    )


@router.get("/analytics/vendors/export.xlsx")
def vendor_analytics_export_xlsx(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "spd_manager", "vendor_user"))):
    rows = _scoped_inspection_rows(db, current_user)
    items = build_vendor_items(rows)
    content = vendor_xlsx_bytes(items)
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=lumenai_vendor_scorecards.xlsx"},
    )


@router.get("/analytics/vendors/export.bundle.zip")
def vendor_analytics_export_bundle(db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "spd_manager", "vendor_user"))):
    rows = _scoped_inspection_rows(db, current_user)
    items = build_vendor_items(rows)

    csv_content = vendor_csv_text(items)
    xlsx_content = vendor_xlsx_bytes(items)
    json_content = json.dumps({"items": items}, indent=2)

    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lumenai_vendor_scorecards.csv", csv_content)
        zf.writestr("lumenai_vendor_scorecards.json", json_content)
        zf.writestr("lumenai_vendor_scorecards.xlsx", xlsx_content)

    bio.seek(0)
    return StreamingResponse(
        bio,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=lumenai_vendor_scorecards_bundle.zip"},
    )


@router.get("/analytics/vendors/{vendor_name}/scorecard.json")
def vendor_scorecard_json(vendor_name: str, db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "spd_manager", "vendor_user"))):
    rows = _scoped_inspection_rows(db, current_user)
    items = build_vendor_items(rows)
    scorecard = find_vendor_scorecard(items, vendor_name)
    if not scorecard:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return JSONResponse(scorecard)


@router.get("/analytics/vendors/{vendor_name}/scorecard.pdf")
def vendor_scorecard_pdf(vendor_name: str, db: Session = Depends(get_db), current_user=Depends(require_roles("admin", "spd_manager", "vendor_user"))):
    rows = _scoped_inspection_rows(db, current_user)
    items = build_vendor_items(rows)
    scorecard = find_vendor_scorecard(items, vendor_name)
    if not scorecard:
        raise HTTPException(status_code=404, detail="Vendor not found")

    pdf_path = generate_vendor_scorecard_pdf(scorecard)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"lumenai_vendor_scorecard_{vendor_name}.pdf",
    )
