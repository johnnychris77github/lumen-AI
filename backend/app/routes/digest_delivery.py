from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any
import csv

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.authz import require_roles
from app.deps import get_db
from app.db import models
from app.notifications.digest_delivery import deliver_digest

router = APIRouter(tags=["digest-delivery"])

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


def _within_days(dt: datetime | None, days: int) -> bool:
    if not dt:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return dt >= now - timedelta(days=days)


def _top_counts(counter: dict[str, int], limit: int = 10):
    return sorted(
        [{"label": k, "count": v} for k, v in counter.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:limit]


def _site_name(row: models.Inspection) -> str:
    return (getattr(row, "site_name", None) or "default-site").strip() or "default-site"


def _vendor_name(row: models.Inspection) -> str:
    return (getattr(row, "vendor_name", None) or "unknown").strip() or "unknown"


def _issue_name(row: models.Inspection) -> str:
    return (getattr(row, "detected_issue", None) or "unknown").strip() or "unknown"


def _rows_for_window(db: Session, current_user: Any, days: int):
    rows = _scoped_inspection_rows(db, current_user)
    return [r for r in rows if _within_days(r.created_at, days)]


def _build_board_report(rows: list[models.Inspection]) -> dict:
    total = len(rows)
    completed = sum(1 for r in rows if (r.status or "").lower() == "completed")
    open_alerts = sum(1 for r in rows if (getattr(r, "alert_status", "open") or "").lower() != "resolved")
    resolved_alerts = sum(1 for r in rows if (getattr(r, "alert_status", "") or "").lower() == "resolved")
    high_risk_count = sum(1 for r in rows if int(getattr(r, "risk_score", 0) or 0) >= 80)
    qa_reviewed = sum(1 for r in rows if (getattr(r, "qa_review_status", "") or "").lower() in {"approved", "overridden"})
    qa_overridden = sum(1 for r in rows if (getattr(r, "qa_review_status", "") or "").lower() == "overridden")

    site_counter: dict[str, int] = {}
    vendor_counter: dict[str, int] = {}
    issue_counter: dict[str, int] = {}

    for r in rows:
        site = _site_name(r)
        vendor = _vendor_name(r)
        issue = _issue_name(r)
        site_counter[site] = site_counter.get(site, 0) + 1
        vendor_counter[vendor] = vendor_counter.get(vendor, 0) + 1
        issue_counter[issue] = issue_counter.get(issue, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "executive_summary": {
            "total_inspections": total,
            "completed": completed,
            "completion_rate": round(completed / total, 4) if total else 0.0,
            "open_alerts": open_alerts,
            "resolved_alerts": resolved_alerts,
            "high_risk_count": high_risk_count,
            "qa_reviewed": qa_reviewed,
            "qa_overridden": qa_overridden,
            "qa_override_rate": round(qa_overridden / qa_reviewed, 4) if qa_reviewed else 0.0,
            "top_sites": _top_counts(site_counter),
            "top_vendors": _top_counts(vendor_counter),
            "top_issues": _top_counts(issue_counter),
        },
        "leadership_narrative": {
            "headline": f"{total} inspections processed in reporting window with {open_alerts} open alerts and {high_risk_count} high-risk findings.",
            "quality_note": f"QA reviewed {qa_reviewed} cases with an override rate of {round((qa_overridden / qa_reviewed) * 100, 1) if qa_reviewed else 0.0}%.",
            "operations_note": f"Top issue trend: {(_top_counts(issue_counter, 1)[0]['label'] if issue_counter else 'none')} | Top site by volume: {(_top_counts(site_counter, 1)[0]['label'] if site_counter else 'none')}.",
        }
    }


def _digest_delivery_response(row: models.DigestDelivery) -> dict:
    return {
        "id": row.id,
        "digest_type": row.digest_type,
        "channel": row.channel,
        "recipients": row.recipients,
        "sent": row.sent,
        "status_code": row.status_code,
        "failure_reason": row.failure_reason,
        "delivery_batch_id": row.delivery_batch_id,
        "payload_summary": row.payload_summary,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/digest-scheduler/run-now")
def run_digest_now(
    days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = _rows_for_window(db, current_user, days)
    digest = _build_board_report(rows)
    result = deliver_digest(db, digest_type="weekly", digest_payload=digest)
    return {
        "digest": digest,
        "delivery": result,
    }


@router.get("/digest-delivery/history")
def digest_delivery_history(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = db.query(models.DigestDelivery).order_by(models.DigestDelivery.id.desc()).limit(limit).all()
    return {"items": [_digest_delivery_response(r) for r in rows]}


@router.get("/digest-delivery/history.csv")
def digest_delivery_history_csv(
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "spd_manager")),
):
    rows = db.query(models.DigestDelivery).order_by(models.DigestDelivery.id.desc()).all()
    items = [_digest_delivery_response(r) for r in rows]

    output = StringIO()
    if items:
        writer = csv.DictWriter(output, fieldnames=list(items[0].keys()))
        writer.writeheader()
        writer.writerows(items)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lumenai_digest_delivery_history.csv"},
    )
