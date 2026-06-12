from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException, Request, status

from app.core.jwt_auth import decode_jwt_unverified, extract_actor_from_jwt, validate_jwt_claims


DEV_TOKEN_ROLES = {
    "dev-token": "admin",
    "spd-manager-token": "spd_manager",
    "vendor-token": "vendor_user",
    "viewer-token": "viewer",
}


def _auth_mode(settings) -> str:
    return str(getattr(settings, "LUMENAI_AUTH_MODE", "dev_token") or "dev_token").strip().lower()


def extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return token


def _dev_actor(token: str):
    role = DEV_TOKEN_ROLES[token]
    return SimpleNamespace(
        id=0,
        actor_id="dev-user",
        actor_name=role,
        actor_email=f"{role}@local",
        actor_role=role,
        email=f"{role}@local",
        role=role,
        tenant_id="",
        tenant_name="",
        token_type="dev_token",
    )


def validate_api_token(token: str, settings):
    token = str(token or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    mode = _auth_mode(settings)

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
            return SimpleNamespace(
                id=0,
                actor_id="api-token",
                actor_name="api-token",
                actor_email="api-token@local",
                actor_role="admin",
                email="api-token@local",
                role="admin",
                tenant_id="",
                tenant_name="",
                token_type="api_token",
            )

    if mode == "jwt":
        payload = decode_jwt_unverified(token)
        validate_jwt_claims(payload, settings)
        return extract_actor_from_jwt(payload)

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


def get_authenticated_actor(request: Request, settings):
    token = extract_bearer_token(request)
    return validate_api_token(token, settings)
