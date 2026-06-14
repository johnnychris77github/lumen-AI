from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import log_audit_event
from app.db import models

SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
SCIM_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
LUMEN_USER_SCHEMA = "urn:ietf:params:scim:schemas:extension:lumen:2.0:User"
LUMEN_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:extension:lumen:2.0:Group"


@dataclass(frozen=True)
class ScimSettings:
    enabled: bool = False
    bearer_token: str = ""
    allowed_tenants: set[str] = field(default_factory=set)
    default_role: str = "viewer"
    allowed_roles: set[str] = field(default_factory=lambda: {"viewer", "reviewer", "vendor_user"})

    @classmethod
    def from_env(cls) -> "ScimSettings":
        return cls(
            enabled=os.getenv("LUMENAI_SCIM_ENABLED", "false").strip().lower() == "true",
            bearer_token=os.getenv("LUMENAI_SCIM_BEARER_TOKEN", "").strip(),
            allowed_tenants=_split_csv(os.getenv("LUMENAI_SCIM_ALLOWED_TENANTS", "")),
            default_role=os.getenv("LUMENAI_SCIM_DEFAULT_ROLE", "viewer").strip() or "viewer",
            allowed_roles=_split_csv(
                os.getenv("LUMENAI_SCIM_ALLOWED_ROLES", "viewer,reviewer,vendor_user")
            )
            or {"viewer", "reviewer", "vendor_user"},
        )


def _split_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def require_scim_auth(request: Request, settings: ScimSettings | None = None) -> ScimSettings:
    settings = settings or ScimSettings.from_env()
    if not settings.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SCIM is not enabled")
    if not settings.bearer_token:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="SCIM is not configured")

    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SCIM credentials")

    token = authorization.split(" ", 1)[1].strip()
    if token != settings.bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid SCIM credentials")
    return settings


def _extension(payload: dict[str, Any], schema: str) -> dict[str, Any]:
    value = payload.get(schema)
    return value if isinstance(value, dict) else {}


def _primary_email(payload: dict[str, Any]) -> str:
    emails = payload.get("emails") or []
    if isinstance(emails, list):
        primary = next((item for item in emails if isinstance(item, dict) and item.get("primary")), None)
        selected = primary or next((item for item in emails if isinstance(item, dict)), None)
        if selected and selected.get("value"):
            return str(selected["value"]).strip().lower()
    return str(payload.get("userName") or payload.get("email") or "").strip().lower()


def _display_name(payload: dict[str, Any]) -> str:
    name = payload.get("name") if isinstance(payload.get("name"), dict) else {}
    formatted = str(name.get("formatted") or "").strip()
    if formatted:
        return formatted
    given = str(name.get("givenName") or "").strip()
    family = str(name.get("familyName") or "").strip()
    return " ".join(part for part in [given, family] if part).strip()


def _tenant_payload(payload: dict[str, Any]) -> tuple[str, str]:
    extension = _extension(payload, LUMEN_USER_SCHEMA)
    tenant_id = str(
        extension.get("tenantId")
        or extension.get("tenant_id")
        or payload.get("tenantId")
        or payload.get("tenant_id")
        or payload.get("externalId")
        or ""
    ).strip()
    tenant_name = str(
        extension.get("tenantName")
        or extension.get("tenant_name")
        or payload.get("tenantName")
        or payload.get("tenant_name")
        or tenant_id
    ).strip()
    return tenant_id, tenant_name or tenant_id


def _requested_role(payload: dict[str, Any], settings: ScimSettings) -> str:
    extension = _extension(payload, LUMEN_USER_SCHEMA)
    role = str(extension.get("role") or payload.get("role") or settings.default_role).strip() or settings.default_role
    if role not in settings.allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SCIM role is not allowed")
    return role


def _ensure_tenant_allowed(tenant_id: str, settings: ScimSettings) -> None:
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SCIM tenant is required")
    if settings.allowed_tenants and tenant_id not in settings.allowed_tenants:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SCIM tenant is not allowed")


def _audit(
    db: Session,
    *,
    action: str,
    tenant_id: str = "",
    tenant_name: str = "",
    resource_id: str = "",
    status_value: str = "success",
    request: Request | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        log_audit_event(
            db,
            tenant_id=tenant_id or "scim",
            tenant_name=tenant_name or tenant_id or "SCIM",
            actor_email="scim-provisioner",
            actor_role="scim",
            action_type=action,
            resource_type="scim",
            resource_id=resource_id,
            status=status_value,
            request=request,
            details=details or {},
            compliance_flag=True,
        )
    except Exception:
        return


def scim_user_response(membership: models.TenantMembership) -> dict[str, Any]:
    return {
        "schemas": [SCIM_USER_SCHEMA, LUMEN_USER_SCHEMA],
        "id": str(membership.id),
        "userName": membership.user_email,
        "active": bool(membership.is_enabled),
        "displayName": membership.user_email,
        "emails": [{"value": membership.user_email, "primary": True}],
        LUMEN_USER_SCHEMA: {
            "tenantId": membership.tenant_id,
            "tenantName": membership.tenant_name,
            "role": membership.role_name,
        },
    }


def list_users(db: Session, settings: ScimSettings) -> dict[str, Any]:
    query = db.query(models.TenantMembership)
    if settings.allowed_tenants:
        query = query.filter(models.TenantMembership.tenant_id.in_(settings.allowed_tenants))
    rows = query.order_by(models.TenantMembership.id.asc()).all()
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(rows),
        "Resources": [scim_user_response(row) for row in rows],
        "startIndex": 1,
        "itemsPerPage": len(rows),
    }


def get_user(db: Session, user_id: str, settings: ScimSettings) -> models.TenantMembership:
    try:
        numeric_id = int(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SCIM user not found") from None

    row = db.query(models.TenantMembership).filter(models.TenantMembership.id == numeric_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SCIM user not found")
    _ensure_tenant_allowed(row.tenant_id, settings)
    return row


def create_or_update_user(
    db: Session,
    payload: dict[str, Any],
    settings: ScimSettings,
    *,
    request: Request | None = None,
) -> models.TenantMembership:
    email = _primary_email(payload)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SCIM userName or email is required")
    tenant_id, tenant_name = _tenant_payload(payload)
    try:
        _ensure_tenant_allowed(tenant_id, settings)
        role = _requested_role(payload, settings)
    except HTTPException as exc:
        _audit(
            db,
            action="scim_provisioning_denied",
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            status_value="denied",
            request=request,
            details={"reason": exc.detail},
        )
        raise
    active = bool(payload.get("active", True))

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = models.User(email=email, hashed_password="scim-managed", role=role)
        db.add(user)
    else:
        user.role = role

    membership = (
        db.query(models.TenantMembership)
        .filter(
            models.TenantMembership.user_email == email,
            models.TenantMembership.tenant_id == tenant_id,
        )
        .first()
    )
    created = membership is None
    if membership is None:
        membership = models.TenantMembership(
            user_email=email,
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            role_name=role,
            is_enabled=active,
        )
        db.add(membership)
    else:
        membership.tenant_name = tenant_name
        membership.role_name = role
        membership.is_enabled = active

    db.commit()
    db.refresh(membership)
    _audit(
        db,
        action="scim_user_created" if created else "scim_user_updated",
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        resource_id=str(membership.id),
        request=request,
        details={"email": email, "role": role, "active": active, "display_name_present": bool(_display_name(payload))},
    )
    return membership


def patch_user(
    db: Session,
    user_id: str,
    payload: dict[str, Any],
    settings: ScimSettings,
    *,
    request: Request | None = None,
) -> models.TenantMembership:
    membership = get_user(db, user_id, settings)
    for operation in payload.get("Operations", []):
        if not isinstance(operation, dict):
            continue
        path = str(operation.get("path") or "").strip().lower()
        value = operation.get("value")
        if path == "active":
            membership.is_enabled = bool(value)
        elif path in {"role", f"{LUMEN_USER_SCHEMA.lower()}:role"}:
            role = str(value or "").strip()
            if role not in settings.allowed_roles:
                _audit(
                    db,
                    action="scim_provisioning_denied",
                    tenant_id=membership.tenant_id,
                    tenant_name=membership.tenant_name,
                    resource_id=str(membership.id),
                    status_value="denied",
                    request=request,
                    details={"reason": "role_not_allowed"},
                )
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SCIM role is not allowed")
            membership.role_name = role

    db.commit()
    db.refresh(membership)
    _audit(
        db,
        action="scim_user_updated",
        tenant_id=membership.tenant_id,
        tenant_name=membership.tenant_name,
        resource_id=str(membership.id),
        request=request,
    )
    return membership


def deactivate_user(
    db: Session,
    user_id: str,
    settings: ScimSettings,
    *,
    request: Request | None = None,
) -> models.TenantMembership:
    membership = get_user(db, user_id, settings)
    membership.is_enabled = False
    db.commit()
    db.refresh(membership)
    _audit(
        db,
        action="scim_user_deactivated",
        tenant_id=membership.tenant_id,
        tenant_name=membership.tenant_name,
        resource_id=str(membership.id),
        request=request,
    )
    return membership


def list_groups(db: Session, settings: ScimSettings) -> dict[str, Any]:
    query = db.query(models.TenantMembership.tenant_id, models.TenantMembership.tenant_name, models.TenantMembership.role_name)
    if settings.allowed_tenants:
        query = query.filter(models.TenantMembership.tenant_id.in_(settings.allowed_tenants))
    rows = query.distinct().all()
    resources = [
        {
            "schemas": [SCIM_GROUP_SCHEMA, LUMEN_GROUP_SCHEMA],
            "id": f"{tenant_id}:{role_name}",
            "displayName": f"{tenant_name} {role_name}",
            LUMEN_GROUP_SCHEMA: {"tenantId": tenant_id, "tenantName": tenant_name, "role": role_name},
        }
        for tenant_id, tenant_name, role_name in rows
    ]
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(resources),
        "Resources": resources,
        "startIndex": 1,
        "itemsPerPage": len(resources),
    }


def _group_tenant_role(payload: dict[str, Any], settings: ScimSettings) -> tuple[str, str, str]:
    extension = _extension(payload, LUMEN_GROUP_SCHEMA)
    tenant_id = str(extension.get("tenantId") or payload.get("tenantId") or "").strip()
    tenant_name = str(extension.get("tenantName") or payload.get("tenantName") or tenant_id).strip()
    role = str(extension.get("role") or payload.get("role") or settings.default_role).strip()
    _ensure_tenant_allowed(tenant_id, settings)
    if role not in settings.allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SCIM role is not allowed")
    return tenant_id, tenant_name or tenant_id, role


def upsert_group(
    db: Session,
    payload: dict[str, Any],
    settings: ScimSettings,
    *,
    request: Request | None = None,
    group_id: str | None = None,
) -> dict[str, Any]:
    try:
        tenant_id, tenant_name, role = _group_tenant_role(payload, settings)
    except HTTPException as exc:
        extension = _extension(payload, LUMEN_GROUP_SCHEMA)
        tenant_id = str(extension.get("tenantId") or payload.get("tenantId") or "").strip()
        tenant_name = str(extension.get("tenantName") or payload.get("tenantName") or tenant_id).strip()
        _audit(
            db,
            action="scim_provisioning_denied",
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            status_value="denied",
            request=request,
            details={"reason": exc.detail},
        )
        raise
    for member in payload.get("members") or []:
        if not isinstance(member, dict):
            continue
        email = str(member.get("value") or member.get("userName") or "").strip().lower()
        if not email:
            continue
        membership = (
            db.query(models.TenantMembership)
            .filter(
                models.TenantMembership.user_email == email,
                models.TenantMembership.tenant_id == tenant_id,
            )
            .first()
        )
        if membership is None:
            membership = models.TenantMembership(
                user_email=email,
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                role_name=role,
                is_enabled=True,
            )
            db.add(membership)
        else:
            membership.role_name = role
            membership.is_enabled = True
    db.commit()
    action = "scim_group_updated" if group_id else "scim_group_created"
    resource_id = group_id or f"{tenant_id}:{role}"
    _audit(
        db,
        action=action,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        resource_id=resource_id,
        request=request,
        details={"role": role, "member_count": len(payload.get("members") or [])},
    )
    return {
        "schemas": [SCIM_GROUP_SCHEMA, LUMEN_GROUP_SCHEMA],
        "id": resource_id,
        "displayName": payload.get("displayName") or f"{tenant_name} {role}",
        LUMEN_GROUP_SCHEMA: {"tenantId": tenant_id, "tenantName": tenant_name, "role": role},
    }
