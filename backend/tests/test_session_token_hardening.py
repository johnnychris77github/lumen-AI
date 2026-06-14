from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import deps
from app.authz import require_roles
from app.core import settings as settings_module
from app.core.session_security import get_authenticated_actor, validate_api_token
from app.db import models


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_settings():
    old_env = settings_module.settings.LUMENAI_ENV
    old_token = settings_module.settings.LUMENAI_API_TOKEN
    old_jwt = settings_module.settings.JWT_SECRET_KEY
    settings_module.settings.LUMENAI_ENV = "development"
    settings_module.settings.LUMENAI_API_TOKEN = ""
    settings_module.settings.JWT_SECRET_KEY = ""
    yield
    settings_module.settings.LUMENAI_ENV = old_env
    settings_module.settings.LUMENAI_API_TOKEN = old_token
    settings_module.settings.JWT_SECRET_KEY = old_jwt


def reset_tables():
    models.AuditLog.__table__.drop(bind=engine, checkfirst=True)
    models.AuditLog.__table__.create(bind=engine)


def make_client(required_role: str = "admin"):
    reset_tables()
    app = FastAPI()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    @app.get("/protected")
    def protected(current_user=Depends(require_roles(required_role))):
        return {
            "email": getattr(current_user, "email", ""),
            "role": getattr(current_user, "role", ""),
        }

    app.dependency_overrides[deps.get_db] = override_get_db
    return TestClient(app)


def auth(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_dev_token_accepted_in_development_and_test_mode():
    client = make_client()

    assert client.get("/protected", headers=auth("dev-token")).status_code == 200

    settings_module.settings.LUMENAI_ENV = "test"
    assert client.get("/protected", headers=auth("dev-token")).status_code == 200


def test_dev_token_rejected_in_production_mode():
    settings_module.settings.LUMENAI_ENV = "production"
    settings_module.settings.LUMENAI_API_TOKEN = "strong-production-token-value"
    client = make_client()

    response = client.get("/protected", headers=auth("dev-token"))

    assert response.status_code == 401
    assert "dev-token" not in response.text


def test_missing_authorization_rejected_on_protected_routes():
    response = make_client().get("/protected")

    assert response.status_code == 401


def test_invalid_bearer_token_rejected():
    response = make_client().get("/protected", headers=auth("not-valid"))

    assert response.status_code == 401


def test_valid_configured_production_token_accepted():
    settings_module.settings.LUMENAI_ENV = "production"
    settings_module.settings.LUMENAI_API_TOKEN = "strong-production-token-value"
    client = make_client()

    response = client.get("/protected", headers=auth("strong-production-token-value"))

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_token_values_are_not_leaked_in_error_responses():
    leaked = "very-sensitive-invalid-token"
    response = make_client().get("/protected", headers=auth(leaked))

    assert response.status_code == 401
    assert leaked not in response.text


def test_401_vs_403_behavior_is_consistent():
    client = make_client(required_role="spd_manager")

    invalid = client.get("/protected", headers=auth("invalid-token"))
    authenticated_but_forbidden = client.get("/protected", headers=auth("dev-token"))

    assert invalid.status_code == 401
    assert authenticated_but_forbidden.status_code == 403


def test_failed_authentication_attempt_is_audited_without_token_value():
    leaked = "sensitive-invalid-token"
    response = make_client().get(
        "/protected",
        headers={**auth(leaked), "X-Tenant-Id": "tenant-a", "X-Tenant-Name": "Tenant A"},
    )

    assert response.status_code == 401
    db = TestingSessionLocal()
    try:
        row = db.query(models.AuditLog).one()
        assert row.tenant_id == "tenant-a"
        assert row.action_type == "authentication_failed"
        assert leaked not in row.details
    finally:
        db.close()


def test_helper_rejects_placeholder_tokens_in_production():
    settings_module.settings.LUMENAI_ENV = "production"
    settings_module.settings.LUMENAI_API_TOKEN = "strong-production-token-value"

    with pytest.raises(Exception):
        validate_api_token("changeme", settings_module.settings)
