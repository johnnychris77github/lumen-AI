from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.settings import settings


LOGGER = logging.getLogger(__name__)
INTERNAL_PROVIDER = "internal"


@dataclass
class AuditAnchorScheduleSummary:
    tenants_seen: int = 0
    anchors_created: int = 0
    tenants_skipped: int = 0
    records_covered: int = 0


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


def _has_table(db: Session, table_name: str) -> bool:
    return table_name in inspect(db.bind).get_table_names()


def _tenant_ids_with_audit_records(db: Session) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT tenant_id
            FROM audit_logs
            GROUP BY tenant_id
            ORDER BY tenant_id ASC
            """
        )
    ).all()
    return [str(row[0] or "") for row in rows]


def _latest_audit_state(db: Session, tenant_id: str) -> dict[str, Any]:
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


def _latest_anchor(db: Session, tenant_id: str):
    return (
        db.execute(
            text(
                """
                SELECT last_audit_log_id
                FROM audit_chain_anchors
                WHERE tenant_id = :tenant_id
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id},
        )
        .mappings()
        .first()
    )


def _insert_anchor(db: Session, tenant_id: str, state: dict[str, Any], provider: str):
    created_at = datetime.now(timezone.utc)
    anchor_hash = calculate_anchor_hash(
        tenant_id=tenant_id,
        last_audit_log_id=state["last_audit_log_id"],
        records_covered=state["records_covered"],
        last_record_hash=state["last_record_hash"],
        timestamp=created_at,
    )
    db.execute(
        text(
            """
            INSERT INTO audit_chain_anchors (
                tenant_id,
                anchor_hash,
                last_audit_log_id,
                records_covered,
                anchor_provider,
                anchor_reference,
                created_at
            )
            VALUES (
                :tenant_id,
                :anchor_hash,
                :last_audit_log_id,
                :records_covered,
                :anchor_provider,
                :anchor_reference,
                :created_at
            )
            """
        ),
        {
            "tenant_id": tenant_id,
            "anchor_hash": anchor_hash,
            "last_audit_log_id": state["last_audit_log_id"],
            "records_covered": state["records_covered"],
            "anchor_provider": provider,
            "anchor_reference": f"internal:{tenant_id}:{state['last_audit_log_id']}:{anchor_hash}",
            "created_at": created_at,
        },
    )
    LOGGER.info(
        "audit_chain_anchor_created",
        extra={
            "tenant_id": tenant_id,
            "last_audit_log_id": state["last_audit_log_id"],
            "records_covered": state["records_covered"],
            "anchor_provider": provider,
        },
    )


def run_scheduled_audit_anchors(db: Session) -> dict[str, int | str]:
    provider = settings.LUMENAI_AUDIT_ANCHOR_PROVIDER
    if provider != INTERNAL_PROVIDER:
        raise ValueError("Only the internal audit anchor provider is supported.")

    if not _has_table(db, "audit_logs") or not _has_table(db, "audit_chain_anchors"):
        return {
            "provider": provider,
            "tenants_seen": 0,
            "anchors_created": 0,
            "tenants_skipped": 0,
            "records_covered": 0,
        }

    summary = AuditAnchorScheduleSummary()

    for tenant_id in _tenant_ids_with_audit_records(db):
        summary.tenants_seen += 1
        state = _latest_audit_state(db, tenant_id)
        latest_anchor = _latest_anchor(db, tenant_id)

        if latest_anchor and state["last_audit_log_id"] <= int(latest_anchor["last_audit_log_id"] or 0):
            summary.tenants_skipped += 1
            continue

        _insert_anchor(db, tenant_id, state, provider)
        summary.anchors_created += 1
        summary.records_covered += state["records_covered"]

    db.commit()
    return {
        "provider": provider,
        "tenants_seen": summary.tenants_seen,
        "anchors_created": summary.anchors_created,
        "tenants_skipped": summary.tenants_skipped,
        "records_covered": summary.records_covered,
    }
