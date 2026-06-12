from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException, Request, status

PLACEHOLDER_TOKENS = {"dev-token", "test-token", "changeme", "secret", "password"}
DEV_TOKEN_ROLES = {
    "dev-token": "admin",
    "spd-manager-token": "spd_manager",
    "vendor-token": "vendor_user",
    "viewer-token": "viewer",
}


def _environment(settings) -> str:
    return str(getattr(settings, "LUMENAI_ENV", "development") or "development").lower()


def _is_production(settings) -> bool:
    return _environment(settings) == "production"


def _configured_api_token(settings) -> str:
    return str(getattr(settings, "LUMENAI_API_TOKEN", "") or "").strip()


def _configured_jwt_secret(settings) -> str:
    return str(getattr(settings, "JWT_SECRET_KEY", "") or "").strip()


def extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
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


def is_dev_token_allowed(settings) -> bool:
    return _environment(settings) in {"development", "test"}


def validate_api_token(token: str, settings):
    token = str(token or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if _is_production(settings):
        if token.lower() in PLACEHOLDER_TOKENS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        configured_token = _configured_api_token(settings)
        if configured_token and token == configured_token:
            return SimpleNamespace(
                id=0,
                email="api-token@local",
                role="admin",
                token_type="configured_api_token",
            )

        if _configured_jwt_secret(settings):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is not configured",
        )

    if token in DEV_TOKEN_ROLES and is_dev_token_allowed(settings):
        role = DEV_TOKEN_ROLES[token]
        return SimpleNamespace(
            id=0,
            email=f"{role}@local",
            role=role,
            token_type="dev_token",
        )

    if token.startswith("user:"):
        email = token.split("user:", 1)[1].strip().lower()
        if email:
            return SimpleNamespace(
                id=None,
                email=email,
                role="db_lookup",
                token_type="user_email",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
    )


def get_authenticated_actor(request: Request, settings):
    token = extract_bearer_token(request)
    return validate_api_token(token, settings)
