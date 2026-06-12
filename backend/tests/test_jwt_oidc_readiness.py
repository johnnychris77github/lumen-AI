from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
from fastapi import HTTPException

from app.core import settings as settings_module
from app.core.jwt_auth import decode_jwt_unverified, extract_actor_from_jwt, validate_jwt_claims
from app.core.session_security import validate_api_token


@pytest.fixture(autouse=True)
def reset_settings():
    original = settings_module.settings.model_copy()
    settings_module.settings.LUMENAI_AUTH_MODE = "dev_token"
    settings_module.settings.LUMENAI_API_TOKEN = ""
    settings_module.settings.LUMENAI_JWT_ISSUER = "https://issuer.example.com"
    settings_module.settings.LUMENAI_JWT_AUDIENCE = "lumen-api"
    settings_module.settings.LUMENAI_JWT_ALGORITHMS = "RS256"
    settings_module.settings.LUMENAI_JWT_JWKS_URL = ""
    settings_module.settings.LUMENAI_JWT_LEEWAY_SECONDS = 30
    yield
    for name, value in original.model_dump().items():
        setattr(settings_module.settings, name, value)


def make_payload(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "iss": "https://issuer.example.com",
        "aud": "lumen-api",
        "sub": "actor-123",
        "name": "Ada Admin",
        "email": "ada@example.com",
        "role": "tenant_admin",
        "tenant_id": "tenant-a",
        "tenant_name": "Tenant A",
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "nbf": int((now - timedelta(minutes=1)).timestamp()),
    }
    payload.update(overrides)
    return payload


def make_token(payload: dict) -> str:
    return jwt.encode(payload, "test-secret", algorithm="HS256")


def test_valid_jwt_claims_pass():
    payload = make_payload()

    validated = validate_jwt_claims(payload, settings_module.settings)

    assert validated["sub"] == "actor-123"


def test_invalid_issuer_fails():
    with pytest.raises(HTTPException) as exc:
        validate_jwt_claims(make_payload(iss="https://wrong.example.com"), settings_module.settings)

    assert exc.value.status_code == 401


def test_invalid_audience_fails():
    with pytest.raises(HTTPException) as exc:
        validate_jwt_claims(make_payload(aud="other-api"), settings_module.settings)

    assert exc.value.status_code == 401


def test_expired_token_fails():
    expired = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())

    with pytest.raises(HTTPException) as exc:
        validate_jwt_claims(make_payload(exp=expired), settings_module.settings)

    assert exc.value.status_code == 401


def test_missing_subject_fails():
    payload = make_payload()
    payload.pop("sub")

    with pytest.raises(HTTPException) as exc:
        validate_jwt_claims(payload, settings_module.settings)

    assert exc.value.status_code == 401


def test_tenant_claim_is_extracted():
    actor = extract_actor_from_jwt(make_payload())

    assert actor.actor_id == "actor-123"
    assert actor.actor_name == "Ada Admin"
    assert actor.actor_email == "ada@example.com"
    assert actor.actor_role == "tenant_admin"
    assert actor.tenant_id == "tenant-a"
    assert actor.tenant_name == "Tenant A"


def test_token_values_are_not_leaked_in_errors():
    secret_token = "very-sensitive-token-value"

    with pytest.raises(HTTPException) as exc:
        decode_jwt_unverified(secret_token)

    assert secret_token not in str(exc.value.detail)


def test_jwt_mode_validates_and_extracts_actor():
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"
    token = make_token(make_payload())

    actor = validate_api_token(token, settings_module.settings)

    assert actor.token_type == "jwt"
    assert actor.email == "ada@example.com"
    assert actor.role == "tenant_admin"


def test_dev_token_mode_still_works():
    settings_module.settings.LUMENAI_AUTH_MODE = "dev_token"

    actor = validate_api_token("dev-token", settings_module.settings)

    assert actor.token_type == "dev_token"
    assert actor.role == "admin"


def test_api_token_mode_still_works():
    settings_module.settings.LUMENAI_AUTH_MODE = "api_token"
    settings_module.settings.LUMENAI_API_TOKEN = "configured-api-token"

    actor = validate_api_token("configured-api-token", settings_module.settings)

    assert actor.token_type == "api_token"
    assert actor.role == "admin"
