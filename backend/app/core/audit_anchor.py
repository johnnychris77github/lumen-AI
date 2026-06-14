from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import models


INTERNAL_ANCHOR_PROVIDER = "internal"


def _timestamp_value(value: datetime) -> str:
    return value.replace(tzinfo=None).isoformat()


def calculate_anchor_hash(
    *,
    tenant_id: str,
    last_audit_log_id: int,
    records_covered: int,
    last_record_hash: str,
    timestamp: datetime,
) -> str:
    payload = {
        "tenant_id": tenant_id,
        "last_audit_log_id": int(last_audit_log_id),
        "records_covered": int(records_covered),
        "last_record_hash": last_record_hash or "",
        "timestamp": _timestamp_value(timestamp),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _latest_audit_state(db: Session, tenant_id: str) -> dict:
    count = int(
        db.execute(
            text("SELECT COUNT(*) FROM audit_logs WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).scalar()
        or 0
    )

    latest = (
        db.execute(
            text(
                """
                SELECT id, record_hash
                FROM audit_logs
                WHERE tenant_id = :tenant_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        .mappings()
        .first()
    )

    return {
        "records_covered": count,
        "last_audit_log_id": int(latest["id"]) if latest else 0,
        "last_record_hash": str(latest["record_hash"] or "") if latest else "",
    }


def create_audit_chain_anchor(
    db: Session,
    tenant_id: str,
    provider: str = INTERNAL_ANCHOR_PROVIDER,
):
    if provider != INTERNAL_ANCHOR_PROVIDER:
        raise ValueError("Only the internal audit anchor provider is supported.")

    state = _latest_audit_state(db, tenant_id)
    created_at = datetime.now(timezone.utc)
    anchor_hash = calculate_anchor_hash(
        tenant_id=tenant_id,
        last_audit_log_id=state["last_audit_log_id"],
        records_covered=state["records_covered"],
        last_record_hash=state["last_record_hash"],
        timestamp=created_at,
    )

    anchor = models.AuditChainAnchor(
        tenant_id=tenant_id,
        anchor_hash=anchor_hash,
        last_audit_log_id=state["last_audit_log_id"],
        records_covered=state["records_covered"],
        anchor_provider=provider,
        anchor_reference=f"internal:{tenant_id}:{state['last_audit_log_id']}:{anchor_hash}",
        created_at=created_at,
    )
    db.add(anchor)
    db.commit()
    db.refresh(anchor)
    return anchor


def list_audit_chain_anchors(db: Session, tenant_id: str):
    return (
        db.query(models.AuditChainAnchor)
        .filter(models.AuditChainAnchor.tenant_id == tenant_id)
        .order_by(models.AuditChainAnchor.created_at.desc(), models.AuditChainAnchor.id.desc())
        .all()
    )
