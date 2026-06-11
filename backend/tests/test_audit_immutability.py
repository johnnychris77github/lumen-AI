from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.audit_logger import append_audit_event
from app.db import models
from app.routes import audit_logs
from app import tenant_authz


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reset_tables() -> None:
    models.TenantMembership.__table__.drop(bind=engine, checkfirst=True)
    models.AuditLog.__table__.drop(bind=engine, checkfirst=True)
    models.AuditLog.__table__.create(bind=engine)
    models.TenantMembership.__table__.create(bind=engine)


def seed_membership(db, user_email: str, tenant_id: str, role_name: str = "tenant_admin"):
    db.add(
        models.TenantMembership(
            user_email=user_email,
            tenant_id=tenant_id,
            tenant_name=f"{tenant_id} name",
            role_name=role_name,
            is_enabled=True,
        )
    )


def append_event(db, tenant_id: str = "tenant-a", action: str = "inspection_create"):
    return append_audit_event(
        db,
        tenant_id=tenant_id,
        tenant_name=f"{tenant_id} name",
        actor_id="actor@example.test",
        actor_name="Actor Example",
        actor_role="tenant_admin",
        action=action,
        resource_type="inspection",
        resource_id="123",
        metadata={"field": "value"},
        compliance_flag=True,
    )


def make_client(current_user):
    app = FastAPI()
    app.include_router(audit_logs.router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[audit_logs.get_db] = override_get_db
    app.dependency_overrides[tenant_authz.get_db] = override_get_db
    app.dependency_overrides[tenant_authz.get_current_user] = lambda: current_user
    return TestClient(app)


def test_audit_records_cannot_be_modified():
    reset_tables()
    db = TestingSessionLocal()
    row = append_event(db)

    row.actor_role = "tampered"
    with pytest.raises(ValueError, match="immutable"):
        db.commit()

    db.rollback()
    unchanged = db.get(models.AuditLog, row.id)
    assert unchanged.actor_role == "tenant_admin"
    db.close()


def test_audit_records_cannot_be_deleted():
    reset_tables()
    db = TestingSessionLocal()
    row = append_event(db)

    db.delete(row)
    with pytest.raises(ValueError, match="immutable"):
        db.commit()

    db.rollback()
    assert db.query(models.AuditLog).count() == 1
    db.close()


def test_new_actions_generate_new_records():
    reset_tables()
    db = TestingSessionLocal()

    first = append_event(db, action="inspection_create")
    second = append_event(db, action="inspection_update")

    assert first.id != second.id
    assert db.query(models.AuditLog).count() == 2
    assert [row.action for row in db.query(models.AuditLog).order_by(models.AuditLog.id).all()] == [
        "inspection_create",
        "inspection_update",
    ]
    db.close()


def test_cross_tenant_audit_access_is_denied():
    reset_tables()
    db = TestingSessionLocal()
    append_event(db, tenant_id="tenant-a")
    seed_membership(db, "member@example.test", "tenant-b")
    db.commit()
    db.close()

    client = make_client(SimpleNamespace(email="member@example.test", role="tenant_admin"))

    response = client.get(
        "/audit-logs",
        headers={"X-Tenant-Id": "tenant-a", "X-Tenant-Name": "Tenant A"},
    )

    assert response.status_code == 403


def test_authorized_tenant_access_succeeds():
    reset_tables()
    db = TestingSessionLocal()
    row = append_event(db, tenant_id="tenant-a")
    row_id = row.id
    seed_membership(db, "member@example.test", "tenant-a")
    db.commit()
    db.close()

    client = make_client(SimpleNamespace(email="member@example.test", role="tenant_admin"))

    response = client.get(
        "/audit-logs",
        headers={"X-Tenant-Id": "tenant-a", "X-Tenant-Name": "Tenant A"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["id"] == row_id
    assert payload["items"][0]["tenant_id"] == "tenant-a"
    assert payload["items"][0]["action"] == "inspection_create"
    assert payload["items"][0]["metadata_json"] == '{"field": "value"}'
