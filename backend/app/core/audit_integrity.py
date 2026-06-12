from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import models


GENESIS_HASH = ""


def ensure_audit_integrity_columns(db: Session) -> None:
    inspector = inspect(db.bind)
    columns = {column["name"] for column in inspector.get_columns(models.AuditLog.__tablename__)}

    missing = []
    if "previous_hash" not in columns:
        missing.append("previous_hash VARCHAR(64) NOT NULL DEFAULT ''")
    if "record_hash" not in columns:
        missing.append("record_hash VARCHAR(64) NOT NULL DEFAULT ''")

    for definition in missing:
        db.execute(text(f"ALTER TABLE {models.AuditLog.__tablename__} ADD COLUMN {definition}"))

    if missing:
        db.commit()


def _timestamp_value(row: models.AuditLog) -> str:
    created_at = getattr(row, "created_at", None)
    if not created_at:
        return ""
    return created_at.replace(tzinfo=None).isoformat()


def _hash_payload(row: models.AuditLog, previous_hash: str) -> dict[str, Any]:
    return {
        "tenant_id": row.tenant_id or "",
        "actor_id": row.actor_email or "",
        "action": row.action_type or "",
        "resource_type": row.resource_type or "",
        "resource_id": row.resource_id or "",
        "timestamp": _timestamp_value(row),
        "metadata_json": row.details or "",
        "previous_hash": previous_hash or "",
    }


def calculate_audit_hash(row: models.AuditLog, previous_hash: str | None = None) -> str:
    payload = _hash_payload(row, previous_hash if previous_hash is not None else row.previous_hash)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _latest_record_hash(db: Session, tenant_id: str) -> str:
    previous = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.tenant_id == tenant_id)
        .order_by(models.AuditLog.id.desc())
        .first()
    )
    return (previous.record_hash if previous else "") or GENESIS_HASH


def attach_audit_hash(db: Session, row: models.AuditLog) -> models.AuditLog:
    ensure_audit_integrity_columns(db)
    row.previous_hash = _latest_record_hash(db, row.tenant_id)
    db.add(row)
    db.flush()
    row.record_hash = calculate_audit_hash(row, row.previous_hash)
    db.add(row)
    return row


def verify_audit_chain(db: Session, tenant_id: str | None = None) -> dict[str, Any]:
    ensure_audit_integrity_columns(db)

    query = db.query(models.AuditLog)
    if tenant_id:
        query = query.filter(models.AuditLog.tenant_id == tenant_id)

    rows = query.order_by(models.AuditLog.tenant_id.asc(), models.AuditLog.id.asc()).all()
    expected_previous_by_tenant: dict[str, str] = {}

    for index, row in enumerate(rows, start=1):
        tenant_key = row.tenant_id or ""
        expected_previous = expected_previous_by_tenant.get(tenant_key, GENESIS_HASH)

        if (row.previous_hash or "") != expected_previous:
            return {
                "valid": False,
                "records_verified": index - 1,
                "invalid": True,
                "first_corrupted_record": row.id,
                "reason": "broken_link",
            }

        expected_hash = calculate_audit_hash(row, row.previous_hash)
        if (row.record_hash or "") != expected_hash:
            return {
                "valid": False,
                "records_verified": index - 1,
                "invalid": True,
                "first_corrupted_record": row.id,
                "reason": "hash_mismatch",
            }

        expected_previous_by_tenant[tenant_key] = row.record_hash or ""

    return {
        "valid": True,
        "records_verified": len(rows),
        "invalid": False,
        "first_corrupted_record": None,
        "reason": "",
    }
