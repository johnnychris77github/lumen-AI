from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import jwt
from fastapi import HTTPException, status


_JWKS_CACHE: dict[str, dict[str, Any]] = {}


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid JWT credentials",
    )


def _allowed_algorithms(settings) -> list[str]:
    raw = str(getattr(settings, "LUMENAI_JWT_ALGORITHMS", "RS256") or "RS256")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _expected_audiences(settings) -> list[str]:
    raw = str(getattr(settings, "LUMENAI_JWT_AUDIENCE", "") or "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _now_seconds() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def clear_jwks_cache() -> None:
    _JWKS_CACHE.clear()


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


def fetch_jwks(settings) -> dict[str, Any]:
    jwks_url = str(getattr(settings, "LUMENAI_JWT_JWKS_URL", "") or "").strip()
    if not jwks_url:
        raise _unauthorized()

    ttl = int(getattr(settings, "LUMENAI_JWKS_CACHE_TTL_SECONDS", 300) or 300)
    now = time.time()
    cached = _JWKS_CACHE.get(jwks_url)
    if cached and now < cached["expires_at"]:
        return cached["jwks"]

    try:
        with urllib.request.urlopen(jwks_url, timeout=5) as response:
            jwks = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise _unauthorized() from exc

    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise _unauthorized()

    _JWKS_CACHE[jwks_url] = {
        "jwks": jwks,
        "expires_at": now + max(ttl, 0),
    }
    return jwks


def get_jwk_for_kid(jwks: dict[str, Any], kid: str) -> dict[str, Any]:
    if not kid:
        raise _unauthorized()

    for key in jwks.get("keys", []):
        if isinstance(key, dict) and key.get("kid") == kid:
            return key

    raise _unauthorized()


def validate_jwt_signature(token: str, settings) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc

    kid = str(header.get("kid") or "")
    if not kid:
        raise _unauthorized()

    alg = str(header.get("alg") or "")
    allowed_algorithms = _allowed_algorithms(settings)
    if alg not in allowed_algorithms:
        raise _unauthorized()

    jwks = fetch_jwks(settings)
    jwk = get_jwk_for_kid(jwks, kid)

    try:
        key = jwt.PyJWK.from_dict(jwk).key
        payload = jwt.decode(
            token,
            key=key,
            algorithms=allowed_algorithms,
            options={
                "verify_aud": False,
                "verify_iss": False,
                "verify_exp": False,
                "verify_nbf": False,
            },
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc

    if not isinstance(payload, dict):
        raise _unauthorized()
    return payload


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


def validate_jwt(token: str, settings) -> dict[str, Any]:
    payload = validate_jwt_signature(token, settings)
    return validate_jwt_claims(payload, settings)


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
