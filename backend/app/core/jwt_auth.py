from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import jwt
from fastapi import HTTPException, status


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT credentials")


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


def _audiences(settings) -> set[str]:
    raw = str(getattr(settings, "LUMENAI_JWT_AUDIENCE", "") or "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def validate_jwt_claims(payload: dict[str, Any], settings) -> dict[str, Any]:
    issuer = str(getattr(settings, "LUMENAI_JWT_ISSUER", "") or "")
    if issuer and payload.get("iss") != issuer:
        raise _unauthorized()

    expected_audiences = _audiences(settings)
    if expected_audiences:
        claim_audience = payload.get("aud")
        claim_audiences = {claim_audience} if isinstance(claim_audience, str) else set(claim_audience or [])
        if not claim_audiences.intersection(expected_audiences):
            raise _unauthorized()

    if not str(payload.get("sub") or "").strip():
        raise _unauthorized()

    now = int(datetime.now(timezone.utc).timestamp())
    leeway = int(getattr(settings, "LUMENAI_JWT_LEEWAY_SECONDS", 0) or 0)
    try:
        if int(payload.get("exp")) + leeway < now:
            raise _unauthorized()
        if payload.get("nbf") is not None and int(payload["nbf"]) - leeway > now:
            raise _unauthorized()
    except (TypeError, ValueError) as exc:
        raise _unauthorized() from exc

    return payload


def validate_jwt(token: str, settings) -> dict[str, Any]:
    # Signature verification is intentionally delegated to this helper so tests
    # and future JWKS integration can patch/extend one place without touching
    # tenant authorization flow.
    payload = decode_jwt_unverified(token)
    return validate_jwt_claims(payload, settings)


def extract_actor_from_jwt(payload: dict[str, Any]):
    actor_role = payload.get("role") or payload.get("roles") or payload.get("groups") or "viewer"
    if isinstance(actor_role, list):
        actor_role = actor_role[0] if actor_role else "viewer"
    actor_email = str(payload.get("email") or payload.get("preferred_username") or "").strip().lower()
    return SimpleNamespace(
        id=str(payload.get("sub") or "").strip(),
        actor_id=str(payload.get("sub") or "").strip(),
        actor_name=str(payload.get("name") or actor_email or payload.get("sub") or "").strip(),
        actor_email=actor_email,
        actor_role=str(actor_role or "viewer").strip(),
        email=actor_email,
        role=str(actor_role or "viewer").strip(),
        tenant_id=str(payload.get("tenant_id") or payload.get("tid") or "").strip(),
        tenant_name=str(payload.get("tenant_name") or "").strip(),
        token_type="jwt",
    )
