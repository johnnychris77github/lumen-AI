from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import jwt
from fastapi import HTTPException, status


def _unauthorized(message: str = "Invalid JWT credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
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


def _expected_audiences(settings) -> list[str]:
    raw = str(getattr(settings, "LUMENAI_JWT_AUDIENCE", "") or "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _now_seconds() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def validate_jwt_claims(payload: dict[str, Any], settings) -> dict[str, Any]:
    issuer = str(getattr(settings, "LUMENAI_JWT_ISSUER", "") or "")
    if issuer and payload.get("iss") != issuer:
        raise _unauthorized()

    audiences = _expected_audiences(settings)
    if audiences:
        claim_audience = payload.get("aud")
        if isinstance(claim_audience, str):
            claim_audiences = {claim_audience}
        elif isinstance(claim_audience, list):
            claim_audiences = {str(item) for item in claim_audience}
        else:
            claim_audiences = set()

        if not claim_audiences.intersection(audiences):
            raise _unauthorized()

    subject = str(payload.get("sub") or "").strip()
    if not subject:
        raise _unauthorized()

    leeway = int(getattr(settings, "LUMENAI_JWT_LEEWAY_SECONDS", 0) or 0)
    now = _now_seconds()

    exp = payload.get("exp")
    if exp is None:
        raise _unauthorized()
    try:
        if int(exp) + leeway < now:
            raise _unauthorized()
    except (TypeError, ValueError) as exc:
        raise _unauthorized() from exc

    nbf = payload.get("nbf")
    if nbf is not None:
        try:
            if int(nbf) - leeway > now:
                raise _unauthorized()
        except (TypeError, ValueError) as exc:
            raise _unauthorized() from exc

    tenant_id = payload.get("tenant_id") or payload.get("tid")
    if tenant_id is not None and not str(tenant_id).strip():
        raise _unauthorized()

    return payload


def extract_actor_from_jwt(payload: dict[str, Any]):
    actor_email = str(payload.get("email") or payload.get("preferred_username") or "").strip().lower()
    actor_role = payload.get("role") or payload.get("roles") or payload.get("groups") or "viewer"
    if isinstance(actor_role, list):
        actor_role = actor_role[0] if actor_role else "viewer"

    return SimpleNamespace(
        actor_id=str(payload.get("sub") or "").strip(),
        actor_name=str(payload.get("name") or actor_email or payload.get("sub") or "").strip(),
        actor_email=actor_email,
        actor_role=str(actor_role or "viewer").strip(),
        tenant_id=str(payload.get("tenant_id") or payload.get("tid") or "").strip(),
        tenant_name=str(payload.get("tenant_name") or "").strip(),
        email=actor_email,
        role=str(actor_role or "viewer").strip(),
        id=str(payload.get("sub") or "").strip(),
        token_type="jwt",
    )
