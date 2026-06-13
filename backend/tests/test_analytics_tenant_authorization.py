from __future__ import annotations

import os
import sys
import types
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

vendor_scorecard_stub = types.ModuleType("app.reports.vendor_scorecard")
vendor_scorecard_stub.generate_vendor_scorecard_pdf = lambda scorecard: "unused.pdf"
sys.modules.setdefault("app.reports.vendor_scorecard", vendor_scorecard_stub)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import deps
from app.db import models
from app.routes import model_performance, review_analytics, site_analytics, tenant_analytics, vendor_analytics


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


def seed_inspection(db, inspection_id: int, tenant_id: str, vendor: str, site: str):
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
            vendor_name=vendor,
            site_name=site,
            qa_review_status="approved",
            qa_reviewer=f"{tenant_id}-reviewer",
        )
    )


def seed_membership(db, *, email: str, tenant_id: str, is_enabled: bool = True):
    db.add(
        models.TenantMembership(
            user_email=email,
            tenant_id=tenant_id,
            tenant_name=f"{tenant_id} name",
            role_name="viewer",
            is_enabled=is_enabled,
        )
    )


def seed_dataset(*, email: str | None = None, tenant_id: str = "tenant-a", enabled: bool = True):
    db = TestingSessionLocal()
    try:
        seed_inspection(db, 1, "tenant-a", "Vendor A", "Site A")
        seed_inspection(db, 2, "tenant-b", "Vendor B", "Site B")
        if email:
            seed_membership(db, email=email, tenant_id=tenant_id, is_enabled=enabled)
        db.commit()
    finally:
        db.close()


def make_client() -> TestClient:
    reset_tables()
    app = FastAPI()
    for router in (
        vendor_analytics.router,
        tenant_analytics.router,
        site_analytics.router,
        review_analytics.router,
        model_performance.router,
    ):
        app.include_router(router)
    for module in (vendor_analytics, tenant_analytics, site_analytics, review_analytics, model_performance):
        app.dependency_overrides[module.get_db] = get_test_db
    app.dependency_overrides[deps.get_db] = get_test_db
    return TestClient(app)


def test_admin_can_see_all_vendor_analytics_rows():
    client = make_client()
    seed_dataset()

    response = client.get("/analytics/vendors", headers=auth("dev-token"))

    assert response.status_code == 200
    assert {item["vendor_name"] for item in response.json()["items"]} == {"Vendor A", "Vendor B"}


def test_enabled_membership_sees_only_that_tenant_in_vendor_analytics():
    client = make_client()
    seed_dataset(email="viewer@local", tenant_id="tenant-a")

    response = client.get("/analytics/vendors", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert [item["vendor_name"] for item in response.json()["items"]] == ["Vendor A"]


def test_vendor_export_excludes_unauthorized_tenant_rows():
    client = make_client()
    seed_dataset(email="vendor_user@local", tenant_id="tenant-a")

    response = client.get("/analytics/vendors/export.json", headers=auth("vendor-token"))

    assert response.status_code == 200
    assert [item["vendor_name"] for item in response.json()["items"]] == ["Vendor A"]


def test_tenant_analytics_rejects_unauthorized_requested_tenant():
    client = make_client()
    seed_dataset(email="spd_manager@local", tenant_id="tenant-a")

    response = client.get(
        "/tenant-analytics/summary",
        headers={**auth("spd-manager-token"), "X-Tenant-ID": "tenant-b"},
    )

    assert response.status_code == 403


def test_site_analytics_excludes_unauthorized_tenant_rows():
    client = make_client()
    seed_dataset(email="spd_manager@local", tenant_id="tenant-a")

    response = client.get("/site-analytics/summary", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    body = response.json()
    assert body["enterprise_summary"]["total_inspections"] == 1
    assert [item["site_name"] for item in body["sites"]] == ["Site A"]


def test_review_analytics_excludes_unauthorized_tenant_rows():
    client = make_client()
    seed_dataset(email="spd_manager@local", tenant_id="tenant-a")

    response = client.get("/review-analytics/feedback-dataset.json", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert [item["vendor_name"] for item in response.json()["items"]] == ["Vendor A"]


def test_model_performance_excludes_unauthorized_tenant_rows():
    client = make_client()
    seed_dataset(email="spd_manager@local", tenant_id="tenant-a")

    response = client.get("/model-performance/export.json", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert [item["vendor_name"] for item in response.json()["feedback_rows"]] == ["Vendor A"]


def test_disabled_membership_returns_no_scoped_analytics_rows():
    client = make_client()
    seed_dataset(email="viewer@local", tenant_id="tenant-a", enabled=False)

    response = client.get("/analytics/vendors", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_no_membership_returns_no_scoped_analytics_rows():
    client = make_client()
    seed_dataset()

    response = client.get("/analytics/vendors", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json()["items"] == []
