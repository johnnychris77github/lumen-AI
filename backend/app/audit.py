from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.audit_logger import append_audit_event


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
    return append_audit_event(
        db,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        actor_id=actor_email,
        actor_name=actor_email,
        actor_role=actor_role,
        action=action_type,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        status=status,
        request=request,
        metadata=details,
        compliance_flag=compliance_flag,
    )
