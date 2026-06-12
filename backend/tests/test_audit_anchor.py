from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import deps
from app.core.audit_anchor import calculate_anchor_hash, create_audit_chain_anchor
from app.db import models
from app.routes.audit_logs import router as audit_logs_router


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reset_tables():
    for model in (models.AuditChainAnchor, models.TenantMembership):
        model.__table__.drop(bind=engine, checkfirst=True)
    metadata = MetaData()
    Table("audit_logs", metadata).drop(bind=engine, checkfirst=True)

    models.TenantMembership.__table__.create(bind=engine)
    metadata = MetaData()
    Table(
        "audit_logs",
        metadata,
        Column("id", models.AuditLog.__table__.c.id.type, primary_key=True),
        Column("tenant_id", String(100), nullable=False),
        Column("record_hash", String(64), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    ).create(bind=engine)
    models.AuditChainAnchor.__table__.create(bind=engine)


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


def auth_headers(tenant_id: str) -> dict[str, str]:
    return {"Authorization": "Bearer dev-token", "X-Tenant-Id": tenant_id}


def seed_membership(tenant_id: str):
    db = TestingSessionLocal()
    try:
        db.add(
            models.TenantMembership(
                user_email="admin@local",
                tenant_id=tenant_id,
                tenant_name=tenant_id.title(),
                role_name="tenant_admin",
                is_enabled=True,
            )
        )
        db.commit()
    finally:
        db.close()


def seed_audit_log(tenant_id: str, log_id: int, record_hash: str):
    db = TestingSessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO audit_logs (id, tenant_id, record_hash, created_at)
                VALUES (:id, :tenant_id, :record_hash, :created_at)
                """
            ),
            {
                "id": log_id,
                "tenant_id": tenant_id,
                "record_hash": record_hash,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            },
        )
        db.commit()
    finally:
        db.close()


def test_anchor_creation_succeeds_for_authorized_tenant():
    client = make_client()
    seed_membership("tenant-a")
    seed_audit_log("tenant-a", 1, "a" * 64)

    response = client.post("/api/audit/integrity/anchor", headers=auth_headers("tenant-a"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == "tenant-a"
    assert payload["anchor_provider"] == "internal"
    assert payload["last_audit_log_id"] == 1
    assert payload["records_covered"] == 1
    assert len(payload["anchor_hash"]) == 64


def test_anchor_includes_latest_audit_record_hash():
    make_client()
    seed_audit_log("tenant-a", 1, "a" * 64)
    seed_audit_log("tenant-a", 2, "b" * 64)

    db = TestingSessionLocal()
    try:
        anchor = create_audit_chain_anchor(db, "tenant-a")
        expected = calculate_anchor_hash(
            tenant_id="tenant-a",
            last_audit_log_id=2,
            records_covered=2,
            last_record_hash="b" * 64,
            timestamp=anchor.created_at,
        )
    finally:
        db.close()

    assert anchor.anchor_hash == expected
    assert anchor.anchor_reference.endswith(anchor.anchor_hash)


def test_cross_tenant_anchor_access_is_denied():
    client = make_client()
    seed_membership("tenant-a")
    seed_audit_log("tenant-b", 1, "b" * 64)

    response = client.post("/api/audit/integrity/anchor", headers=auth_headers("tenant-b"))

    assert response.status_code == 403


def test_anchor_history_is_tenant_isolated():
    client = make_client()
    seed_membership("tenant-a")
    seed_audit_log("tenant-a", 1, "a" * 64)
    seed_audit_log("tenant-b", 2, "b" * 64)

    db = TestingSessionLocal()
    try:
        create_audit_chain_anchor(db, "tenant-a")
        create_audit_chain_anchor(db, "tenant-b")
    finally:
        db.close()

    response = client.get("/api/audit/integrity/anchors", headers=auth_headers("tenant-a"))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["tenant_id"] == "tenant-a"


def test_anchor_hash_is_deterministic_for_same_inputs():
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    first = calculate_anchor_hash(
        tenant_id="tenant-a",
        last_audit_log_id=42,
        records_covered=10,
        last_record_hash="c" * 64,
        timestamp=timestamp,
    )
    second = calculate_anchor_hash(
        tenant_id="tenant-a",
        last_audit_log_id=42,
        records_covered=10,
        last_record_hash="c" * 64,
        timestamp=timestamp,
    )

    assert first == second


def test_internal_anchor_requires_no_external_network_calls(monkeypatch):
    make_client()
    seed_audit_log("tenant-a", 1, "a" * 64)

    def fail_network(*args, **kwargs):
        raise AssertionError("network calls are not expected for internal anchors")

    monkeypatch.setattr("socket.create_connection", fail_network)

    db = TestingSessionLocal()
    try:
        anchor = create_audit_chain_anchor(db, "tenant-a")
    finally:
        db.close()

    assert anchor.anchor_provider == "internal"
