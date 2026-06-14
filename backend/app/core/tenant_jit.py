from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.audit import log_audit_event
from app.db import models


def _csv_set(value: str) -> set[str]:
    return {item.strip().lower() for item in str(value or "").split(",") if item.strip()}


def _actor_value(actor, *names: str) -> str:
    for name in names:
        value = getattr(actor, name, None)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _safe_domain(email: str) -> str:
    return email.rsplit("@", 1)[1].lower() if "@" in email else ""


def _audit(
    db: Session,
    *,
    tenant_id: str,
    tenant_name: str,
    actor_email: str,
    actor_role: str,
    action_type: str,
    status_value: str,
    reason: str,
):
    log_audit_event(
        db,
        tenant_id=tenant_id or "default-tenant",
        tenant_name=tenant_name or tenant_id or "Default Tenant",
        actor_email=actor_email,
        actor_role=actor_role,
        action_type=action_type,
        resource_type="tenant_membership",
        resource_id=tenant_id,
        status=status_value,
        details={"reason": reason},
        compliance_flag=True,
    )


def _deny(
    db: Session,
    *,
    tenant_id: str,
    tenant_name: str,
    actor_email: str,
    actor_role: str,
    action_type: str = "tenant_jit_membership_denied",
    reason: str,
):
    _audit(
        db,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        actor_email=actor_email,
        actor_role=actor_role,
        action_type=action_type,
        status_value="denied",
        reason=reason,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Tenant JIT provisioning denied",
    )


def provision_tenant_membership_from_claims(db: Session, actor, settings):
    if not bool(getattr(settings, "LUMENAI_TENANT_JIT_ENABLED", False)):
        return None

    actor_email = _actor_value(actor, "actor_email", "email").lower()
    actor_role = _actor_value(actor, "actor_role", "role") or "viewer"
    tenant_id = _actor_value(actor, "tenant_id")
    tenant_name = _actor_value(actor, "tenant_name") or tenant_id

    if bool(getattr(settings, "LUMENAI_TENANT_JIT_REQUIRE_TENANT_CLAIM", True)) and not tenant_id:
        _deny(
            db,
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            actor_email=actor_email,
            actor_role=actor_role,
            reason="missing_tenant_claim",
        )

    allowed_domains = _csv_set(getattr(settings, "LUMENAI_TENANT_JIT_ALLOWED_DOMAINS", ""))
    if allowed_domains and _safe_domain(actor_email) not in allowed_domains:
        _deny(
            db,
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            actor_email=actor_email,
            actor_role=actor_role,
            reason="disallowed_email_domain",
        )

    allowed_roles = _csv_set(getattr(settings, "LUMENAI_TENANT_JIT_ALLOWED_ROLES", "viewer,reviewer,admin"))
    requested_role = (actor_role or "").lower()
    default_role = str(getattr(settings, "LUMENAI_TENANT_JIT_DEFAULT_ROLE", "viewer") or "viewer").lower()
    role_to_assign = requested_role or default_role

    if role_to_assign not in allowed_roles:
        _deny(
            db,
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            actor_email=actor_email,
            actor_role=actor_role,
            reason="disallowed_role",
        )

    membership = (
        db.query(models.TenantMembership)
        .filter(
            models.TenantMembership.user_email == actor_email,
            models.TenantMembership.tenant_id == tenant_id,
        )
        .first()
    )
    if membership:
        existing_role = (membership.role_name or "").lower()
        if existing_role != role_to_assign and role_to_assign in allowed_roles:
            _audit(
                db,
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                actor_email=actor_email,
                actor_role=actor_role,
                action_type="tenant_jit_role_escalation_blocked",
                status_value="blocked",
                reason="existing_membership_not_escalated",
            )
        return membership

    membership = models.TenantMembership(
        user_email=actor_email,
        tenant_id=tenant_id,
        tenant_name=tenant_name or tenant_id,
        role_name=role_to_assign,
        is_enabled=True,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    _audit(
        db,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        actor_email=actor_email,
        actor_role=role_to_assign,
        action_type="tenant_jit_membership_created",
        status_value="success",
        reason="membership_created",
    )
    return membership
