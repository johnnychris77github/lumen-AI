from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
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
from app.routes import board_reporting, digest_delivery, executive_digest


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reset_tables():
    for model in (models.DigestDelivery, models.Inspection, models.TenantMembership):
        model.__table__.drop(bind=engine, checkfirst=True)
    for model in (models.TenantMembership, models.Inspection, models.DigestDelivery):
        model.__table__.create(bind=engine)


def get_test_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_inspection(db, inspection_id: int, tenant_id: str, site: str):
    db.add(
        models.Inspection(
            id=inspection_id,
            created_at=datetime.now(timezone.utc),
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
            site_name=site,
            qa_review_status="approved",
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
        seed_inspection(db, 1, "tenant-a", "Site A")
        seed_inspection(db, 2, "tenant-b", "Site B")
        if tenant_id:
            seed_membership(db, tenant_id=tenant_id, is_enabled=enabled)
        db.commit()
    finally:
        db.close()


def make_client(monkeypatch) -> TestClient:
    reset_tables()
    monkeypatch.setattr(
        digest_delivery,
        "deliver_digest",
        lambda db, digest_type, digest_payload: {
            "sent": True,
            "payload_total": digest_payload["executive_summary"]["total_inspections"],
        },
    )

    app = FastAPI()
    for router in (board_reporting.router, digest_delivery.router, executive_digest.router):
        app.include_router(router)
    for module in (board_reporting, digest_delivery, executive_digest):
        app.dependency_overrides[module.get_db] = get_test_db
    app.dependency_overrides[deps.get_db] = get_test_db
    return TestClient(app)


def test_board_weekly_report_excludes_unauthorized_tenant_rows(monkeypatch):
    client = make_client(monkeypatch)
    seed_dataset(tenant_id="tenant-a")

    response = client.get("/board-reporting/weekly", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert response.json()["executive_summary"]["total_inspections"] == 1
    assert response.json()["executive_summary"]["top_sites"][0]["label"] == "Site A"


def test_digest_run_now_is_tenant_scoped(monkeypatch):
    client = make_client(monkeypatch)
    seed_dataset(tenant_id="tenant-a")

    response = client.post("/digest-scheduler/run-now", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert response.json()["digest"]["executive_summary"]["total_inspections"] == 1
    assert response.json()["delivery"]["payload_total"] == 1


def test_executive_digest_weekly_is_tenant_scoped(monkeypatch):
    client = make_client(monkeypatch)
    seed_dataset(tenant_id="tenant-a")

    response = client.get("/executive-digest/weekly", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert response.json()["executive_summary"]["total_inspections"] == 1
    assert response.json()["site_benchmark"][0]["site_name"] == "Site A"


def test_disabled_membership_returns_empty_reporting_payloads(monkeypatch):
    client = make_client(monkeypatch)
    seed_dataset(tenant_id="tenant-a", enabled=False)

    response = client.get("/board-reporting/weekly", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert response.json()["executive_summary"]["total_inspections"] == 0


def test_no_membership_returns_empty_reporting_payloads(monkeypatch):
    client = make_client(monkeypatch)
    seed_dataset(tenant_id=None)

    response = client.get("/executive-digest/weekly", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    assert response.json()["executive_summary"]["total_inspections"] == 0
