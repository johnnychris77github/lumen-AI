from __future__ import annotations

import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
from fastapi import HTTPException

from app.core import jwt_auth
from app.core import settings as settings_module


SECRET = b"local-test-signing-secret"
JWKS_URL = "https://issuer.example.com/.well-known/jwks.json"


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


@pytest.fixture(autouse=True)
def reset_settings():
    original = settings_module.settings.model_copy()
    jwt_auth.clear_jwks_cache()
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"
    settings_module.settings.LUMENAI_JWT_ISSUER = "https://issuer.example.com"
    settings_module.settings.LUMENAI_JWT_AUDIENCE = "lumen-api"
    settings_module.settings.LUMENAI_JWT_ALGORITHMS = "HS256"
    settings_module.settings.LUMENAI_JWT_JWKS_URL = JWKS_URL
    settings_module.settings.LUMENAI_JWT_LEEWAY_SECONDS = 30
    settings_module.settings.LUMENAI_JWKS_CACHE_TTL_SECONDS = 300
    yield
    jwt_auth.clear_jwks_cache()
    for name, value in original.model_dump().items():
        setattr(settings_module.settings, name, value)


def jwks(kid: str = "kid-1", secret: bytes = SECRET) -> dict:
    encoded = base64.urlsafe_b64encode(secret).decode("ascii").rstrip("=")
    return {"keys": [{"kty": "oct", "kid": kid, "k": encoded, "alg": "HS256"}]}


def payload(**overrides):
    now = datetime.now(timezone.utc)
    data = {
        "iss": "https://issuer.example.com",
        "aud": "lumen-api",
        "sub": "actor-123",
        "email": "ada@example.com",
        "tenant_id": "tenant-a",
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "nbf": int((now - timedelta(minutes=1)).timestamp()),
    }
    data.update(overrides)
    return data


def token(kid: str | None = "kid-1", algorithm: str = "HS256", claims: dict | None = None) -> str:
    headers = {}
    if kid is not None:
        headers["kid"] = kid
    return jwt.encode(claims or payload(), SECRET, algorithm=algorithm, headers=headers)


def install_jwks(monkeypatch, jwks_payload: dict):
    calls = {"count": 0}

    def fake_urlopen(url, timeout=5):
        assert url == JWKS_URL
        calls["count"] += 1
        return FakeResponse(jwks_payload)

    monkeypatch.setattr(jwt_auth.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_valid_signed_jwt_passes(monkeypatch):
    install_jwks(monkeypatch, jwks())

    decoded = jwt_auth.validate_jwt(token(), settings_module.settings)

    assert decoded["sub"] == "actor-123"
    assert decoded["tenant_id"] == "tenant-a"


def test_unknown_kid_fails(monkeypatch):
    install_jwks(monkeypatch, jwks(kid="other-kid"))

    with pytest.raises(HTTPException) as exc:
        jwt_auth.validate_jwt(token(kid="kid-1"), settings_module.settings)

    assert exc.value.status_code == 401


def test_unsupported_algorithm_fails(monkeypatch):
    install_jwks(monkeypatch, jwks())
    settings_module.settings.LUMENAI_JWT_ALGORITHMS = "RS256"

    with pytest.raises(HTTPException) as exc:
        jwt_auth.validate_jwt(token(algorithm="HS256"), settings_module.settings)

    assert exc.value.status_code == 401


def test_missing_kid_fails(monkeypatch):
    install_jwks(monkeypatch, jwks())

    with pytest.raises(HTTPException) as exc:
        jwt_auth.validate_jwt(token(kid=None), settings_module.settings)

    assert exc.value.status_code == 401


def test_jwks_cache_is_used(monkeypatch):
    calls = install_jwks(monkeypatch, jwks())

    jwt_auth.validate_jwt(token(), settings_module.settings)
    jwt_auth.validate_jwt(token(), settings_module.settings)

    assert calls["count"] == 1


def test_cache_refreshes_after_ttl(monkeypatch):
    calls = install_jwks(monkeypatch, jwks())
    settings_module.settings.LUMENAI_JWKS_CACHE_TTL_SECONDS = 1
    current_time = {"value": 1000.0}
    monkeypatch.setattr(jwt_auth.time, "time", lambda: current_time["value"])

    jwt_auth.validate_jwt(token(), settings_module.settings)
    current_time["value"] = 1002.0
    jwt_auth.validate_jwt(token(), settings_module.settings)

    assert calls["count"] == 2


def test_network_failure_is_sanitized(monkeypatch):
    sensitive = token()

    def fail_urlopen(url, timeout=5):
        raise OSError("network unavailable")

    monkeypatch.setattr(jwt_auth.urllib.request, "urlopen", fail_urlopen)

    with pytest.raises(HTTPException) as exc:
        jwt_auth.validate_jwt(sensitive, settings_module.settings)

    assert exc.value.status_code == 401
    assert sensitive not in str(exc.value.detail)


def test_claim_validation_still_applies_after_signature_validation(monkeypatch):
    install_jwks(monkeypatch, jwks())

    with pytest.raises(HTTPException) as exc:
        jwt_auth.validate_jwt(token(claims=payload(iss="https://wrong.example.com")), settings_module.settings)

    assert exc.value.status_code == 401
