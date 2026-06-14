from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import requests
from sqlalchemy.orm import Session

from app.db import models


class AuditAnchorError(RuntimeError):
    """Safe audit anchor failure that never includes provider tokens or secrets."""


@dataclass(frozen=True)
class AuditAnchorSettings:
    provider: str = "internal"
    external_url: str = ""
    external_token: str = ""
    timeout_seconds: float = 3.0
    fail_mode: str = "internal_fallback"

    @classmethod
    def from_env(cls) -> "AuditAnchorSettings":
        return cls(
            provider=os.getenv("LUMENAI_AUDIT_ANCHOR_PROVIDER", "internal").strip().lower() or "internal",
            external_url=os.getenv("LUMENAI_AUDIT_ANCHOR_EXTERNAL_URL", "").strip(),
            external_token=os.getenv("LUMENAI_AUDIT_ANCHOR_EXTERNAL_TOKEN", "").strip(),
            timeout_seconds=float(os.getenv("LUMENAI_AUDIT_ANCHOR_TIMEOUT_SECONDS", "3.0")),
            fail_mode=os.getenv("LUMENAI_AUDIT_ANCHOR_FAIL_MODE", "internal_fallback").strip().lower()
            or "internal_fallback",
        )


@dataclass(frozen=True)
class AnchorMaterial:
    tenant_id: str
    anchor_hash: str
    timestamp: str
    last_audit_log_id: int
    records_covered: int


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _audit_records(db: Session, tenant_id: str) -> list[models.AuditLog]:
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.tenant_id == tenant_id)
        .order_by(models.AuditLog.created_at.asc(), models.AuditLog.id.asc())
        .all()
    )


def _record_digest(row: models.AuditLog) -> str:
    payload = {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "actor_email": row.actor_email,
        "actor_role": row.actor_role,
        "action_type": row.action_type,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def build_anchor_material(db: Session, tenant_id: str, timestamp: datetime | None = None) -> AnchorMaterial:
    rows = _audit_records(db, tenant_id)
    if not rows:
        raise AuditAnchorError("No audit records available to anchor")

    timestamp = timestamp or datetime.now(timezone.utc)
    last_row = rows[-1]
    chain_digest = hashlib.sha256("".join(_record_digest(row) for row in rows).encode("utf-8")).hexdigest()
    anchor_payload = {
        "tenant_id": tenant_id,
        "last_audit_log_id": last_row.id,
        "records_covered": len(rows),
        "last_record_digest": _record_digest(last_row),
        "chain_digest": chain_digest,
        "timestamp": timestamp.isoformat(),
    }
    return AnchorMaterial(
        tenant_id=tenant_id,
        anchor_hash=hashlib.sha256(_canonical_json(anchor_payload).encode("utf-8")).hexdigest(),
        timestamp=timestamp.isoformat(),
        last_audit_log_id=last_row.id,
        records_covered=len(rows),
    )


def _safe_external_reference(response: Any) -> str:
    try:
        data = response.json()
    except Exception:
        data = {}

    for key in ("anchor_reference", "reference", "id", "receipt_id", "timestamp_token"):
        value = data.get(key) if isinstance(data, dict) else None
        if value:
            return str(value)[:500]

    headers = getattr(response, "headers", {}) or {}
    request_id = headers.get("x-request-id") or headers.get("X-Request-ID")
    if request_id:
        return str(request_id)[:500]
    return f"external_http_status_{getattr(response, 'status_code', 'unknown')}"


def _post_external_anchor(
    material: AnchorMaterial,
    settings: AuditAnchorSettings,
    http_post: Callable[..., Any],
) -> str:
    if not settings.external_url:
        raise AuditAnchorError("External audit anchor provider is not configured")

    payload = {
        "anchor_hash": material.anchor_hash,
        "tenant_id": material.tenant_id,
        "timestamp": material.timestamp,
        "last_audit_log_id": material.last_audit_log_id,
        "records_covered": material.records_covered,
    }
    headers = {"Content-Type": "application/json"}
    if settings.external_token:
        headers["Authorization"] = f"Bearer {settings.external_token}"

    try:
        response = http_post(
            settings.external_url,
            json=payload,
            headers=headers,
            timeout=settings.timeout_seconds,
        )
        response.raise_for_status()
    except Exception as exc:
        raise AuditAnchorError("External audit anchor provider failed") from exc

    return _safe_external_reference(response)


def create_audit_chain_anchor(
    db: Session,
    tenant_id: str,
    *,
    provider: str | None = None,
    settings: AuditAnchorSettings | None = None,
    http_post: Callable[..., Any] | None = None,
    timestamp: datetime | None = None,
) -> models.AuditChainAnchor:
    settings = settings or AuditAnchorSettings.from_env()
    selected_provider = (provider or settings.provider or "internal").strip().lower()
    material = build_anchor_material(db, tenant_id, timestamp)
    anchor_provider = "internal"
    anchor_reference = "internal"

    if selected_provider == "external_http":
        try:
            anchor_reference = _post_external_anchor(material, settings, http_post or requests.post)
            anchor_provider = "external_http"
        except AuditAnchorError:
            if settings.fail_mode == "fail_closed":
                raise AuditAnchorError("External audit anchor provider failed")
            anchor_provider = "internal"
            anchor_reference = "internal_fallback"
    elif selected_provider != "internal":
        raise AuditAnchorError("Unsupported audit anchor provider")

    row = models.AuditChainAnchor(
        tenant_id=tenant_id,
        anchor_hash=material.anchor_hash,
        last_audit_log_id=material.last_audit_log_id,
        records_covered=material.records_covered,
        anchor_provider=anchor_provider,
        anchor_reference=anchor_reference,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
