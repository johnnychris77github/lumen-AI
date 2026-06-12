from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import jwt
from fastapi import HTTPException, status


PROVIDER_PROFILES: dict[str, dict[str, list[str]]] = {
    "generic": {
        "actor_id": ["sub"],
        "actor_name": ["name"],
        "actor_email": ["email", "preferred_username"],
        "actor_role": ["role", "roles", "groups"],
        "tenant_id": ["tenant_id", "tid"],
        "tenant_name": ["tenant_name"],
    },
    "azure_ad": {
        "actor_id": ["oid", "sub"],
        "actor_name": ["name"],
        "actor_email": ["preferred_username", "upn", "email"],
        "actor_role": ["roles", "groups"],
        "tenant_id": ["tid", "tenant_id"],
        "tenant_name": ["tenant_name"],
    },
    "okta": {
        "actor_id": ["sub"],
        "actor_name": ["name"],
        "actor_email": ["email"],
        "actor_role": ["groups", "roles", "role"],
        "tenant_id": ["tenant_id", "tid"],
        "tenant_name": ["tenant_name", "organization.name"],
    },
    "auth0": {
        "actor_id": ["sub"],
        "actor_name": ["name"],
        "actor_email": ["email"],
        "actor_role": ["permissions", "roles", "role"],
        "tenant_id": ["tenant_id", "org_id", "https://lumenai.example/tenant_id"],
        "tenant_name": ["tenant_name", "org_name", "https://lumenai.example/tenant_name"],
    },
    "custom": {
        "actor_id": ["sub"],
        "actor_name": ["name"],
        "actor_email": ["email"],
        "actor_role": ["role", "roles", "groups"],
        "tenant_id": ["tenant_id", "tid"],
        "tenant_name": ["tenant_name"],
    },
}


SETTING_OVERRIDES = {
    "actor_id": "LUMENAI_JWT_ACTOR_ID_CLAIM",
    "actor_name": "LUMENAI_JWT_ACTOR_NAME_CLAIM",
    "actor_email": "LUMENAI_JWT_ACTOR_EMAIL_CLAIM",
    "actor_role": "LUMENAI_JWT_ROLE_CLAIM",
    "tenant_id": "LUMENAI_JWT_TENANT_ID_CLAIM",
    "tenant_name": "LUMENAI_JWT_TENANT_NAME_CLAIM",
}


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid JWT credentials",
    )


def decode_jwt_unverified(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_aud": False,
                "verify_iss": False,
                "verify_exp": False,
                "verify_nbf": False,
            },
            algorithms=None,
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc

    if not isinstance(payload, dict):
        raise _unauthorized()
    return payload


def _claim_path_value(payload: dict[str, Any], path: str) -> Any:
    if path in payload:
        return payload[path]

    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _first_claim_value(payload: dict[str, Any], paths: list[str]) -> Any:
    for path in paths:
        value = _claim_path_value(payload, path)
        if value not in (None, ""):
            return value
    return None


def _profile_name(settings) -> str:
    configured = str(getattr(settings, "LUMENAI_OIDC_PROVIDER", "generic") or "generic").lower()
    return configured if configured in PROVIDER_PROFILES else "generic"


def _claim_paths(settings, normalized_name: str) -> list[str]:
    override_setting = SETTING_OVERRIDES[normalized_name]
    override = str(getattr(settings, override_setting, "") or "").strip()
    if override:
        return [item.strip() for item in override.split(",") if item.strip()]
    return PROVIDER_PROFILES[_profile_name(settings)][normalized_name]


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    return str(value).strip()


def _role_value(value: Any) -> str:
    if value is None:
        return "viewer"
    if isinstance(value, list):
        strings = [str(item).strip() for item in value if str(item).strip()]
        return strings[0] if strings else "viewer"
    return str(value).strip() or "viewer"


def extract_actor_from_jwt(payload: dict[str, Any], settings=None):
    if settings is None:
        from app.core.settings import settings as default_settings

        settings = default_settings

    actor_id = _string_value(_first_claim_value(payload, _claim_paths(settings, "actor_id")))
    if not actor_id:
        raise _unauthorized()

    actor_email = _string_value(_first_claim_value(payload, _claim_paths(settings, "actor_email"))).lower()
    actor_name = _string_value(_first_claim_value(payload, _claim_paths(settings, "actor_name")))
    actor_role = _role_value(_first_claim_value(payload, _claim_paths(settings, "actor_role")))
    tenant_id = _string_value(_first_claim_value(payload, _claim_paths(settings, "tenant_id")))
    tenant_name = _string_value(_first_claim_value(payload, _claim_paths(settings, "tenant_name")))

    return SimpleNamespace(
        actor_id=actor_id,
        actor_name=actor_name or actor_email or actor_id,
        actor_email=actor_email,
        actor_role=actor_role,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        id=actor_id,
        email=actor_email,
        role=actor_role,
        token_type="jwt",
    )


def validate_jwt_claims(payload: dict[str, Any], settings) -> dict[str, Any]:
    extract_actor_from_jwt(payload, settings)
    return payload
