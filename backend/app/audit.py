from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.audit_integrity import attach_audit_hash
from app.db import models


def log_audit_event(
    db: Session,
    *,
    tenant_id: str,
    tenant_name: str,
    actor_email: str,
    actor_role: str,
    action_type: str,
    resource_type: str = "",
    resource_id: str = "",
    status: str = "success",
    request: Request | None = None,
    details: dict[str, Any] | None = None,
    compliance_flag: bool = False,
):
    row = models.AuditLog(
        tenant_id=tenant_id or "default-tenant",
        tenant_name=tenant_name or "Default Tenant",
        actor_email=(actor_email or "").strip().lower(),
        actor_role=actor_role or "",
        action_type=action_type,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        status=status,
        request_method=request.method if request else "",
        request_path=str(request.url.path) if request else "",
        client_ip=(request.client.host if request and request.client else ""),
        details=json.dumps(details or {}, default=str)[:4000],
        compliance_flag=bool(compliance_flag),
    )
    attach_audit_hash(db, row)
    db.commit()
    db.refresh(row)
    return row
