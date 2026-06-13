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

from app import deps
from app.db import models
from app.routes import agent


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reset_tables():
    for model in (models.Inspection, models.TenantMembership):
        model.__table__.drop(bind=engine, checkfirst=True)
    for model in (models.TenantMembership, models.Inspection):
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
    app.include_router(agent.router)
    app.dependency_overrides[agent.get_db] = get_test_db
    app.dependency_overrides[deps.get_db] = get_test_db
    return TestClient(app)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_inspection(db, inspection_id: int, tenant_id: str):
    db.add(
        models.Inspection(
            id=inspection_id,
            tenant_id=tenant_id,
            tenant_name=f"{tenant_id} name",
            file_name=f"{tenant_id}-{inspection_id}.jpg",
            stain_detected=True,
            confidence=0.95,
            material_type="steel",
            status="completed",
            instrument_type="forceps",
            detected_issue="debris",
            risk_score=90,
            vendor_name=f"Vendor {tenant_id}",
            site_name="site-a",
        )
    )


def seed_membership(db, *, tenant_id: str, is_enabled: bool = True):
    db.add(
        models.TenantMembership(
            user_email="viewer@local",
            tenant_id=tenant_id,
            tenant_name=f"{tenant_id} name",
            role_name="viewer",
            is_enabled=is_enabled,
        )
    )


def seed_dataset(*, membership_tenant: str | None = None, membership_enabled: bool = True):
    db = TestingSessionLocal()
    try:
        seed_inspection(db, 1, "tenant-a")
        seed_inspection(db, 2, "tenant-b")
        if membership_tenant:
            seed_membership(db, tenant_id=membership_tenant, is_enabled=membership_enabled)
        db.commit()
    finally:
        db.close()


def feed_ids(response):
    assert response.status_code == 200
    return sorted(item["inspection_id"] for item in response.json()["items"])


def test_unauthenticated_agent_feed_returns_401():
    client = make_client()
    seed_dataset()

    response = client.get("/agent/feed")

    assert response.status_code == 401


def test_unauthenticated_agent_inspection_returns_401():
    client = make_client()
    seed_dataset()

    response = client.get("/agent/inspection/1")

    assert response.status_code == 401


def test_admin_can_access_all_agent_feed_rows():
    client = make_client()
    seed_dataset()

    response = client.get("/agent/feed", headers=auth("dev-token"))

    assert feed_ids(response) == [1, 2]


def test_enabled_tenant_membership_sees_only_that_tenant_in_agent_feed():
    client = make_client()
    seed_dataset(membership_tenant="tenant-a")

    response = client.get("/agent/feed", headers=auth("viewer-token"))

    assert feed_ids(response) == [1]


def test_cross_tenant_agent_inspection_returns_403():
    client = make_client()
    seed_dataset(membership_tenant="tenant-a")

    response = client.get("/agent/inspection/2", headers=auth("viewer-token"))

    assert response.status_code == 403


def test_missing_agent_inspection_returns_404():
    client = make_client()
    seed_dataset(membership_tenant="tenant-a")

    response = client.get("/agent/inspection/999", headers=auth("viewer-token"))

    assert response.status_code == 404


def test_disabled_membership_sees_no_agent_feed_rows():
    client = make_client()
    seed_dataset(membership_tenant="tenant-a", membership_enabled=False)

    response = client.get("/agent/feed", headers=auth("viewer-token"))

    assert feed_ids(response) == []


def test_no_membership_sees_no_agent_feed_rows():
    client = make_client()
    seed_dataset()

    response = client.get("/agent/feed", headers=auth("viewer-token"))

    assert feed_ids(response) == []


def test_authorized_agent_inspection_preserves_response_shape():
    client = make_client()
    seed_dataset(membership_tenant="tenant-a")

    response = client.get("/agent/inspection/1", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert set(response.json()) == {
        "inspection_id",
        "priority",
        "risk_score",
        "escalation_needed",
        "recommended_actions",
        "summary",
    }
    assert response.json()["inspection_id"] == 1
