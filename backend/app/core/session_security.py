from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.jwt_auth import extract_actor_from_jwt, validate_jwt
from app.core.tenant_jit import provision_tenant_membership_from_claims
from app.db import models


DEV_TOKEN_ROLES = {
    "dev-token": "admin",
    "spd-manager-token": "spd_manager",
    "vendor-token": "vendor_user",
    "viewer-token": "viewer",
}


def _mode(settings) -> str:
    return str(getattr(settings, "LUMENAI_AUTH_MODE", "dev_token") or "dev_token").lower()


def extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return token


def _audit_auth_event(db: Session | None, actor, action: str, status_value: str, reason: str = "") -> None:
    if db is None:
        return
    try:
        db.add(
            models.AuditLog(
                tenant_id=getattr(actor, "tenant_id", "") or "default-tenant",
                tenant_name=getattr(actor, "tenant_name", "") or "Default Tenant",
                actor_email=getattr(actor, "email", "") or getattr(actor, "actor_email", ""),
                actor_role=getattr(actor, "role", "") or getattr(actor, "actor_role", ""),
                action_type=action,
                resource_type="authentication",
                resource_id=getattr(actor, "tenant_id", "") or "",
                status=status_value,
                details=f'{{"reason":"{reason}"}}' if reason else "{}",
                compliance_flag=True,
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def _dev_actor(token: str):
    role = DEV_TOKEN_ROLES[token]
    return SimpleNamespace(id=0, email=f"{role}@local", role=role, token_type="dev_token")


def validate_api_token(token: str, settings):
    token = str(token or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    mode = _mode(settings)
    if mode == "dev_token":
        if token in DEV_TOKEN_ROLES:
            return _dev_actor(token)
        if token.startswith("user:"):
            email = token.split("user:", 1)[1].strip().lower()
            if email:
                return SimpleNamespace(email=email, role="db_lookup", token_type="user_email")

    if mode == "api_token":
        configured = str(getattr(settings, "LUMENAI_API_TOKEN", "") or "").strip()
        if configured and token == configured:
            return SimpleNamespace(id=0, email="api-token@local", role="admin", token_type="api_token")

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


def authenticate_request(request: Request, db: Session | None, settings):
    token = extract_bearer_token(request)
    mode = _mode(settings)

    if mode in {"dev_token", "api_token"}:
        return validate_api_token(token, settings)

    if mode != "jwt":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    try:
        payload = validate_jwt(token, settings)
        actor = extract_actor_from_jwt(payload)
    except HTTPException:
        _audit_auth_event(db, SimpleNamespace(), "jwt_auth_failed", "failed", "invalid_jwt")
        raise

    membership = None
    if db is not None and actor.tenant_id and actor.email:
        membership = (
            db.query(models.TenantMembership)
            .filter(
                models.TenantMembership.user_email == actor.email,
                models.TenantMembership.tenant_id == actor.tenant_id,
                models.TenantMembership.is_enabled == True,
            )
            .first()
        )

    if not membership and db is not None:
        _audit_auth_event(db, actor, "jwt_jit_provisioning_attempted", "attempted")
        try:
            membership = provision_tenant_membership_from_claims(db, actor, settings)
        except HTTPException:
            _audit_auth_event(db, actor, "jwt_tenant_authorization_denied", "denied", "no_membership")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant authorization denied")

    if db is not None and not membership:
        _audit_auth_event(db, actor, "jwt_tenant_authorization_denied", "denied", "no_membership")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant authorization denied")

    if membership:
        actor.role = membership.role_name
        actor.actor_role = membership.role_name
        actor.tenant_name = membership.tenant_name

    _audit_auth_event(db, actor, "jwt_auth_success", "success")
    return actor
