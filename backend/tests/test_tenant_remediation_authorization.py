from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models
from app.routes import tenant_remediations as remediation_routes


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

REMEDIATIONS = [
    {"id": 10, "tenant_id": 1, "action_title": "Fix A", "status": "open", "priority": "high", "due_date": None},
    {"id": 20, "tenant_id": 2, "action_title": "Fix B", "status": "open", "priority": "critical", "due_date": None},
]


def reset_tables():
    models.TenantMembership.__table__.drop(bind=engine, checkfirst=True)
    models.TenantMembership.__table__.create(bind=engine)


def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_membership(*, tenant_id: str = "1", is_enabled: bool = True):
    db = TestingSessionLocal()
    try:
        db.add(
            models.TenantMembership(
                user_email="viewer@local",
                tenant_id=tenant_id,
                tenant_name=f"Tenant {tenant_id}",
                role_name="viewer",
                is_enabled=is_enabled,
            )
        )
        db.commit()
    finally:
        db.close()


def make_client(monkeypatch) -> TestClient:
    reset_tables()

    def list_rows(db, status=None, tenant_id=None, overdue_only=False, limit=100):
        rows = REMEDIATIONS
        if status:
            rows = [row for row in rows if row["status"] == status]
        if tenant_id:
            rows = [row for row in rows if row["tenant_id"] == tenant_id]
        return rows[:limit]

    monkeypatch.setattr(remediation_routes, "list_tenant_remediations", list_rows)
    monkeypatch.setattr(
        remediation_routes,
        "get_tenant_remediation",
        lambda db, remediation_id: next((row for row in REMEDIATIONS if row["id"] == remediation_id), None),
    )
    monkeypatch.setattr(
        remediation_routes,
        "update_tenant_remediation",
        lambda db, remediation_id, updates: {
            **next(row for row in REMEDIATIONS if row["id"] == remediation_id),
            **updates,
        },
    )
    monkeypatch.setattr(remediation_routes, "create_tenant_remediation", lambda **kwargs: {"id": 30, **kwargs})
    monkeypatch.setattr(remediation_routes, "create_remediations_from_tenant_insight", lambda db, tenant_id: [{"id": 40, "tenant_id": tenant_id}])

    app = FastAPI()
    app.include_router(remediation_routes.router)
    app.dependency_overrides[remediation_routes.get_db] = get_test_db
    return TestClient(app)


def test_non_admin_remediation_list_is_tenant_scoped(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.get("/tenant-remediations", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [10]


def test_non_admin_disabled_membership_sees_no_remediations(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1", is_enabled=False)

    response = client.get("/tenant-remediations", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json() == []


def test_non_admin_remediation_rollup_is_tenant_scoped(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.get("/tenant-remediations/rollup", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["high_priority"] == 1
    assert response.json()["critical_priority"] == 0


def test_cross_tenant_remediation_get_returns_403(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.get("/tenant-remediations/20", headers=auth("viewer-token"))

    assert response.status_code == 403


def test_cross_tenant_remediation_patch_returns_403(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.patch(
        "/tenant-remediations/20",
        json={"status": "blocked"},
        headers=auth("viewer-token"),
    )

    assert response.status_code == 403


def test_cross_tenant_remediation_close_returns_403(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.post("/tenant-remediations/20/close", headers=auth("viewer-token"))

    assert response.status_code == 403


def test_from_insight_cross_tenant_creation_returns_403(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.post("/tenant-remediations/from-insight/2", headers=auth("viewer-token"))

    assert response.status_code == 403


def test_create_payload_tenant_id_must_be_authorized(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.post(
        "/tenant-remediations",
        json={"tenant_id": 2, "action_title": "Cross tenant"},
        headers=auth("viewer-token"),
    )

    assert response.status_code == 403
