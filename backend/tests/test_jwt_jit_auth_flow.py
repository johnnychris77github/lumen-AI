from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import deps
from app.authz import require_roles
from app.core import settings as settings_module
from app.db import models


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_settings():
    original = settings_module.settings.model_copy()
    settings_module.settings.LUMENAI_AUTH_MODE = "dev_token"
    settings_module.settings.LUMENAI_API_TOKEN = ""
    settings_module.settings.LUMENAI_JWT_ISSUER = "https://issuer.example.com"
    settings_module.settings.LUMENAI_JWT_AUDIENCE = "lumen-api"
    settings_module.settings.LUMENAI_JWT_LEEWAY_SECONDS = 30
    settings_module.settings.LUMENAI_TENANT_JIT_ENABLED = False
    settings_module.settings.LUMENAI_TENANT_JIT_ALLOWED_DOMAINS = ""
    settings_module.settings.LUMENAI_TENANT_JIT_DEFAULT_ROLE = "viewer"
    settings_module.settings.LUMENAI_TENANT_JIT_ALLOWED_ROLES = "viewer,reviewer,admin"
    settings_module.settings.LUMENAI_TENANT_JIT_REQUIRE_TENANT_CLAIM = True
    yield
    for name, value in original.model_dump().items():
        setattr(settings_module.settings, name, value)


@pytest.fixture(autouse=True)
def reset_tables():
    for model in (models.AuditLog, models.TenantMembership, models.User):
        model.__table__.drop(bind=engine, checkfirst=True)
    for model in (models.User, models.TenantMembership, models.AuditLog):
        model.__table__.create(bind=engine)
    yield


def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_client(required_role: str = "viewer") -> TestClient:
    app = FastAPI()

    @app.get("/protected")
    def protected(current_user=Depends(require_roles(required_role))):
        return {
            "email": getattr(current_user, "email", ""),
            "role": getattr(current_user, "role", ""),
            "tenant_id": getattr(current_user, "tenant_id", ""),
        }

    app.dependency_overrides[deps.get_db] = get_test_db
    return TestClient(app)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_token(**overrides) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "iss": "https://issuer.example.com",
        "aud": "lumen-api",
        "sub": "actor-1",
        "email": "ada@example.com",
        "role": "viewer",
        "tenant_id": "tenant-a",
        "tenant_name": "Tenant A",
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    payload.update(overrides)
    return jwt.encode(payload, "test-secret", algorithm="HS256")


def seed_membership(email: str = "ada@example.com", tenant_id: str = "tenant-a", role: str = "viewer"):
    db = TestingSessionLocal()
    try:
        db.add(
            models.TenantMembership(
                user_email=email,
                tenant_id=tenant_id,
                tenant_name=tenant_id.title(),
                role_name=role,
                is_enabled=True,
            )
        )
        db.commit()
    finally:
        db.close()


def memberships():
    db = TestingSessionLocal()
    try:
        return [
            (row.user_email, row.tenant_id, row.role_name)
            for row in db.query(models.TenantMembership).order_by(models.TenantMembership.tenant_id.asc()).all()
        ]
    finally:
        db.close()


def test_dev_token_mode_still_works():
    response = make_client(required_role="admin").get("/protected", headers=auth("dev-token"))

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_api_token_mode_still_works():
    settings_module.settings.LUMENAI_AUTH_MODE = "api_token"
    settings_module.settings.LUMENAI_API_TOKEN = "configured-api-token"

    response = make_client(required_role="admin").get("/protected", headers=auth("configured-api-token"))

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_jwt_mode_rejects_missing_token():
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"

    response = make_client().get("/protected")

    assert response.status_code == 401


def test_jwt_mode_rejects_invalid_token():
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"

    response = make_client().get("/protected", headers=auth("not-a-jwt"))

    assert response.status_code == 401
    assert "not-a-jwt" not in response.text


def test_jwt_mode_allows_valid_token_with_existing_membership():
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"
    seed_membership(role="reviewer")

    response = make_client(required_role="reviewer").get("/protected", headers=auth(make_token(role="admin")))

    assert response.status_code == 200
    assert response.json()["role"] == "reviewer"


def test_jwt_mode_provisions_membership_when_jit_enabled_and_allowed():
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"
    settings_module.settings.LUMENAI_TENANT_JIT_ENABLED = True
    settings_module.settings.LUMENAI_TENANT_JIT_ALLOWED_DOMAINS = "example.com"

    response = make_client().get("/protected", headers=auth(make_token(role="viewer")))

    assert response.status_code == 200
    assert memberships() == [("ada@example.com", "tenant-a", "viewer")]


def test_jwt_mode_denies_when_jit_disabled():
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"

    response = make_client().get("/protected", headers=auth(make_token()))

    assert response.status_code == 403


def test_jwt_mode_denies_disallowed_role_domain():
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"
    settings_module.settings.LUMENAI_TENANT_JIT_ENABLED = True
    settings_module.settings.LUMENAI_TENANT_JIT_ALLOWED_DOMAINS = "example.com"
    settings_module.settings.LUMENAI_TENANT_JIT_ALLOWED_ROLES = "viewer"

    domain_response = make_client().get("/protected", headers=auth(make_token(email="ada@evil.test")))
    role_response = make_client().get("/protected", headers=auth(make_token(role="admin")))

    assert domain_response.status_code == 403
    assert role_response.status_code == 403


def test_no_role_escalation_occurs():
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"
    settings_module.settings.LUMENAI_TENANT_JIT_ENABLED = True
    seed_membership(role="viewer")

    response = make_client(required_role="admin").get("/protected", headers=auth(make_token(role="admin")))

    assert response.status_code == 403
    assert memberships() == [("ada@example.com", "tenant-a", "viewer")]


def test_errors_do_not_leak_token_or_sensitive_claim_values():
    settings_module.settings.LUMENAI_AUTH_MODE = "jwt"
    sensitive = "sensitive-claim-value"
    token = make_token(email=sensitive, tenant_id="")

    response = make_client().get("/protected", headers=auth(token))

    assert response.status_code == 403
    assert token not in response.text
    assert sensitive not in response.text
