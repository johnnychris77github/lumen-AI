from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import settings as settings_module
from app.core.tenant_jit import provision_tenant_membership_from_claims
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
    for model in (models.AuditLog, models.TenantMembership):
        model.__table__.drop(bind=engine, checkfirst=True)
    for model in (models.TenantMembership, models.AuditLog):
        model.__table__.create(bind=engine)
    yield


def actor(
    *,
    email: str = "ada@example.com",
    role: str = "viewer",
    tenant_id: str = "tenant-a",
    tenant_name: str = "Tenant A",
):
    return SimpleNamespace(
        actor_email=email,
        email=email,
        actor_role=role,
        role=role,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
    )


def db_session():
    return TestingSessionLocal()


def enable_jit():
    settings_module.settings.LUMENAI_TENANT_JIT_ENABLED = True


def audit_actions(db):
    return [row.action_type for row in db.query(models.AuditLog).order_by(models.AuditLog.id.asc()).all()]


def test_jit_disabled_by_default():
    db = db_session()
    try:
        result = provision_tenant_membership_from_claims(db, actor(), settings_module.settings)
        count = db.query(models.TenantMembership).count()
    finally:
        db.close()

    assert result is None
    assert count == 0


def test_valid_claims_create_membership_when_enabled():
    enable_jit()
    db = db_session()
    try:
        membership = provision_tenant_membership_from_claims(db, actor(role="reviewer"), settings_module.settings)
        membership_values = {
            "user_email": membership.user_email,
            "tenant_id": membership.tenant_id,
            "role_name": membership.role_name,
            "is_enabled": membership.is_enabled,
        }
    finally:
        db.close()

    assert membership_values == {
        "user_email": "ada@example.com",
        "tenant_id": "tenant-a",
        "role_name": "reviewer",
        "is_enabled": True,
    }


def test_missing_tenant_claim_fails_when_required():
    enable_jit()
    db = db_session()
    try:
        with pytest.raises(HTTPException) as exc:
            provision_tenant_membership_from_claims(db, actor(tenant_id=""), settings_module.settings)
        actions = audit_actions(db)
    finally:
        db.close()

    assert exc.value.status_code == 403
    assert actions == ["tenant_jit_membership_denied"]


def test_disallowed_email_domain_fails():
    enable_jit()
    settings_module.settings.LUMENAI_TENANT_JIT_ALLOWED_DOMAINS = "example.com"
    db = db_session()
    try:
        with pytest.raises(HTTPException):
            provision_tenant_membership_from_claims(db, actor(email="ada@evil.test"), settings_module.settings)
        actions = audit_actions(db)
    finally:
        db.close()

    assert actions == ["tenant_jit_membership_denied"]


def test_disallowed_role_fails():
    enable_jit()
    settings_module.settings.LUMENAI_TENANT_JIT_ALLOWED_ROLES = "viewer,reviewer"
    db = db_session()
    try:
        with pytest.raises(HTTPException):
            provision_tenant_membership_from_claims(db, actor(role="admin"), settings_module.settings)
        actions = audit_actions(db)
    finally:
        db.close()

    assert actions == ["tenant_jit_membership_denied"]


def test_existing_membership_is_not_escalated():
    enable_jit()
    db = db_session()
    try:
        db.add(
            models.TenantMembership(
                user_email="ada@example.com",
                tenant_id="tenant-a",
                tenant_name="Tenant A",
                role_name="viewer",
                is_enabled=True,
            )
        )
        db.commit()
        membership = provision_tenant_membership_from_claims(db, actor(role="admin"), settings_module.settings)
        role_name = membership.role_name
        actions = audit_actions(db)
    finally:
        db.close()

    assert role_name == "viewer"
    assert actions == ["tenant_jit_role_escalation_blocked"]


def test_audit_event_written_for_created_and_denied_attempts():
    enable_jit()
    settings_module.settings.LUMENAI_TENANT_JIT_ALLOWED_DOMAINS = "example.com"
    db = db_session()
    try:
        provision_tenant_membership_from_claims(db, actor(email="ada@example.com"), settings_module.settings)
        with pytest.raises(HTTPException):
            provision_tenant_membership_from_claims(
                db,
                actor(email="bad@evil.test", tenant_id="tenant-b", tenant_name="Tenant B"),
                settings_module.settings,
            )
        actions = audit_actions(db)
    finally:
        db.close()

    assert actions == ["tenant_jit_membership_created", "tenant_jit_membership_denied"]


def test_cross_tenant_behavior_remains_isolated():
    enable_jit()
    db = db_session()
    try:
        first = provision_tenant_membership_from_claims(db, actor(tenant_id="tenant-a"), settings_module.settings)
        second = provision_tenant_membership_from_claims(db, actor(tenant_id="tenant-b", tenant_name="Tenant B"), settings_module.settings)
        memberships = (
            db.query(models.TenantMembership)
            .filter(models.TenantMembership.user_email == "ada@example.com")
            .order_by(models.TenantMembership.tenant_id.asc())
            .all()
        )
    finally:
        db.close()

    assert first.tenant_id == "tenant-a"
    assert second.tenant_id == "tenant-b"
    assert [membership.tenant_id for membership in memberships] == ["tenant-a", "tenant-b"]
