from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import deps
from app.audit import log_audit_event
from app.core.audit_integrity import verify_audit_chain
from app.db import models
from app.routes.audit_logs import router as audit_logs_router


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reset_tables():
    for model in (models.TenantMembership, models.User, models.AuditLog):
        model.__table__.drop(bind=engine, checkfirst=True)
    for model in (models.AuditLog, models.User, models.TenantMembership):
        model.__table__.create(bind=engine)


def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_client() -> TestClient:
    reset_tables()
    app = FastAPI()
    app.include_router(audit_logs_router, prefix="/api")
    app.dependency_overrides[deps.get_db] = get_test_db
    return TestClient(app)


def seed_membership(tenant_id: str, role_name: str = "tenant_admin"):
    db = TestingSessionLocal()
    try:
        db.add(
            models.TenantMembership(
                user_email="admin@local",
                tenant_id=tenant_id,
                tenant_name=tenant_id.title(),
                role_name=role_name,
                is_enabled=True,
            )
        )
        db.commit()
    finally:
        db.close()


def add_audit_event(tenant_id: str, action: str = "create"):
    db = TestingSessionLocal()
    try:
        row = log_audit_event(
            db,
            tenant_id=tenant_id,
            tenant_name=tenant_id.title(),
            actor_email="actor@example.com",
            actor_role="tenant_admin",
            action_type=action,
            resource_type="inspection",
            resource_id=f"{tenant_id}-{action}",
            details={"action": action, "tenant_id": tenant_id},
        )
        return row.id, row.previous_hash, row.record_hash
    finally:
        db.close()


def test_chain_creation_links_new_records():
    make_client()

    first_id, first_previous, first_hash = add_audit_event("tenant-a", "create")
    second_id, second_previous, second_hash = add_audit_event("tenant-a", "update")

    assert first_id != second_id
    assert first_previous == ""
    assert len(first_hash) == 64
    assert second_previous == first_hash
    assert len(second_hash) == 64


def test_chain_verification_succeeds_for_valid_chain():
    make_client()
    add_audit_event("tenant-a", "create")
    add_audit_event("tenant-a", "update")

    db = TestingSessionLocal()
    try:
        result = verify_audit_chain(db, "tenant-a")
    finally:
        db.close()

    assert result["valid"] is True
    assert result["records_verified"] == 2
    assert result["first_corrupted_record"] is None


def test_tamper_detection_flags_changed_record_payload():
    make_client()
    first_id, _, _ = add_audit_event("tenant-a", "create")

    db = TestingSessionLocal()
    try:
        db.execute(
            text("UPDATE audit_logs SET details = :details WHERE id = :id"),
            {"details": '{"tampered": true}', "id": first_id},
        )
        db.commit()

        result = verify_audit_chain(db, "tenant-a")
    finally:
        db.close()

    assert result["valid"] is False
    assert result["reason"] == "hash_mismatch"
    assert result["first_corrupted_record"] == first_id


def test_broken_link_detection_flags_previous_hash_change():
    make_client()
    add_audit_event("tenant-a", "create")
    second_id, _, _ = add_audit_event("tenant-a", "update")

    db = TestingSessionLocal()
    try:
        db.execute(
            text("UPDATE audit_logs SET previous_hash = :previous_hash WHERE id = :id"),
            {"previous_hash": "0" * 64, "id": second_id},
        )
        db.commit()

        result = verify_audit_chain(db, "tenant-a")
    finally:
        db.close()

    assert result["valid"] is False
    assert result["reason"] == "broken_link"
    assert result["first_corrupted_record"] == second_id


def test_tenant_isolation_for_verification_and_endpoint_access():
    client = make_client()
    seed_membership("tenant-a")
    add_audit_event("tenant-a", "create")
    tenant_b_id, _, _ = add_audit_event("tenant-b", "create")

    db = TestingSessionLocal()
    try:
        db.execute(
            text("UPDATE audit_logs SET details = :details WHERE id = :id"),
            {"details": '{"tampered": true}', "id": tenant_b_id},
        )
        db.commit()

        tenant_a_result = verify_audit_chain(db, "tenant-a")
        tenant_b_result = verify_audit_chain(db, "tenant-b")
    finally:
        db.close()

    assert tenant_a_result["valid"] is True
    assert tenant_b_result["valid"] is False

    authorized = client.get(
        "/api/audit/integrity",
        headers={"Authorization": "Bearer dev-token", "X-Tenant-Id": "tenant-a"},
    )
    denied = client.get(
        "/api/audit/integrity",
        headers={"Authorization": "Bearer dev-token", "X-Tenant-Id": "tenant-b"},
    )

    assert authorized.status_code == 200
    assert authorized.json()["chain_status"] == "valid"
    assert authorized.json()["records_verified"] == 1
    assert denied.status_code == 403
