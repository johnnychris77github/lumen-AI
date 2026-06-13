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
from app.routes import qa_review


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
            qa_review_status="pending",
        )
    )


def seed_membership(db, *, tenant_id: str, is_enabled: bool = True):
    db.add(
        models.TenantMembership(
            user_email="spd_manager@local",
            tenant_id=tenant_id,
            tenant_name=f"{tenant_id} name",
            role_name="viewer",
            is_enabled=is_enabled,
        )
    )


def seed_dataset(*, tenant_id: str | None = "tenant-a", enabled: bool = True):
    db = TestingSessionLocal()
    try:
        seed_inspection(db, 1, "tenant-a")
        seed_inspection(db, 2, "tenant-b")
        if tenant_id:
            seed_membership(db, tenant_id=tenant_id, is_enabled=enabled)
        db.commit()
    finally:
        db.close()


def make_client() -> TestClient:
    reset_tables()
    app = FastAPI()
    app.include_router(qa_review.router)
    app.dependency_overrides[qa_review.get_db] = get_test_db
    app.dependency_overrides[deps.get_db] = get_test_db
    return TestClient(app)


def test_qa_pending_list_excludes_unauthorized_tenant_rows():
    client = make_client()
    seed_dataset(tenant_id="tenant-a")

    response = client.get("/qa-review/pending", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [1]


def test_qa_review_mutation_returns_403_for_cross_tenant_inspection_id():
    client = make_client()
    seed_dataset(tenant_id="tenant-a")

    response = client.post(
        "/qa-review/2",
        json={"notes": "reviewed", "approve_model": True},
        headers=auth("spd-manager-token"),
    )

    assert response.status_code == 403


def test_qa_review_mutation_returns_404_for_missing_inspection_id():
    client = make_client()
    seed_dataset(tenant_id="tenant-a")

    response = client.post(
        "/qa-review/999",
        json={"notes": "reviewed", "approve_model": True},
        headers=auth("spd-manager-token"),
    )

    assert response.status_code == 404


def test_disabled_membership_sees_no_pending_reviews():
    client = make_client()
    seed_dataset(tenant_id="tenant-a", enabled=False)

    response = client.get("/qa-review/pending", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_no_membership_sees_no_pending_reviews():
    client = make_client()
    seed_dataset(tenant_id=None)

    response = client.get("/qa-review/pending", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert response.json()["items"] == []
