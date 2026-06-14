from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db import models


def _csv_set(value: str) -> set[str]:
    return {item.strip().lower() for item in str(value or "").split(",") if item.strip()}


def _domain(email: str) -> str:
    return email.rsplit("@", 1)[1].lower() if "@" in email else ""


def provision_tenant_membership_from_claims(db: Session, actor, settings):
    if not bool(getattr(settings, "LUMENAI_TENANT_JIT_ENABLED", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant authorization denied")

    tenant_id = str(getattr(actor, "tenant_id", "") or "").strip()
    tenant_name = str(getattr(actor, "tenant_name", "") or tenant_id).strip()
    actor_email = str(getattr(actor, "actor_email", None) or getattr(actor, "email", "") or "").strip().lower()
    actor_role = str(getattr(actor, "actor_role", None) or getattr(actor, "role", "") or "").strip().lower()

    if bool(getattr(settings, "LUMENAI_TENANT_JIT_REQUIRE_TENANT_CLAIM", True)) and not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant authorization denied")

    allowed_domains = _csv_set(getattr(settings, "LUMENAI_TENANT_JIT_ALLOWED_DOMAINS", ""))
    if allowed_domains and _domain(actor_email) not in allowed_domains:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant authorization denied")

    allowed_roles = _csv_set(getattr(settings, "LUMENAI_TENANT_JIT_ALLOWED_ROLES", "viewer,reviewer,admin"))
    default_role = str(getattr(settings, "LUMENAI_TENANT_JIT_DEFAULT_ROLE", "viewer") or "viewer").lower()
    role_to_assign = actor_role or default_role
    if role_to_assign not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant authorization denied")

    existing = (
        db.query(models.TenantMembership)
        .filter(
            models.TenantMembership.user_email == actor_email,
            models.TenantMembership.tenant_id == tenant_id,
        )
        .first()
    )
    if existing:
        return existing

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
    return membership
