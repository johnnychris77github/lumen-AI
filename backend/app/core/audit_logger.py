from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.db import models


def _json_text(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, default=str)[:4000]


def _request_source(request: Request | None) -> str:
    if not request:
        return ""
    client_ip = request.client.host if request.client else ""
    return " ".join(
        part
        for part in [
            request.method,
            str(request.url.path),
            client_ip,
        ]
        if part
    )[:500]


def append_audit_event(
    db: Session,
    *,
    tenant_id: str,
    tenant_name: str,
    actor_id: str = "",
    actor_name: str = "",
    actor_role: str = "",
    action: str,
    resource_type: str,
    resource_id: str,
    request: Request | None = None,
    request_source: str | None = None,
    metadata: dict[str, Any] | None = None,
    status: str = "success",
    compliance_flag: bool = False,
) -> models.AuditLog:
    timestamp = datetime.now(timezone.utc)
    actor_id = str(actor_id or "").strip().lower()
    actor_name = str(actor_name or actor_id or "").strip()
    metadata_json = _json_text(metadata)
    source = (request_source or _request_source(request))[:500]

    row = models.AuditLog(
        tenant_id=tenant_id or "default-tenant",
        tenant_name=tenant_name or "Default Tenant",
        actor_id=actor_id,
        actor_name=actor_name,
        actor_email=actor_id,
        actor_role=actor_role or "",
        action=action,
        action_type=action,
        resource_type=resource_type or "",
        resource_id=str(resource_id or ""),
        timestamp_utc=timestamp,
        request_source=source,
        metadata_json=metadata_json,
        status=status,
        request_method=request.method if request else "",
        request_path=str(request.url.path) if request else "",
        client_ip=(request.client.host if request and request.client else ""),
        details=metadata_json,
        compliance_flag=bool(compliance_flag),
        created_at=timestamp,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
