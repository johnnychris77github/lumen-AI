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
from app.routes.alerts import router as alerts_router


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reset_tables():
    for model in (models.AlertEvent, models.Inspection, models.TenantMembership):
        model.__table__.drop(bind=engine, checkfirst=True)
    for model in (models.TenantMembership, models.Inspection, models.AlertEvent):
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
    app.include_router(alerts_router)
    app.dependency_overrides[deps.get_db] = get_test_db
    return TestClient(app)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def seed_inspection(
    db,
    inspection_id: int,
    tenant_id: str,
    *,
    alert_status: str = "open",
    risk_score: int = 90,
):
    row = models.Inspection(
        id=inspection_id,
        tenant_id=tenant_id,
        tenant_name=tenant_id.title(),
        file_name=f"{tenant_id}-{inspection_id}.jpg",
        stain_detected=True,
        confidence=0.95,
        material_type="steel",
        status="flagged",
        instrument_type="forceps",
        detected_issue="debris",
        risk_score=risk_score,
        vendor_name=f"Vendor {tenant_id}",
        site_name="site-a",
        alert_status=alert_status,
    )
    db.add(row)
    return row


def seed_alert_event(db, event_id: int, inspection_id: int, tenant_id: str):
    row = models.AlertEvent(
        id=event_id,
        inspection_id=inspection_id,
        vendor_name=f"Vendor {tenant_id}",
        instrument_type="forceps",
        detected_issue="debris",
        risk_score=90,
        channel="email",
        sent=True,
        status_code="200",
        failure_reason="",
        dispatch_batch_id=f"batch-{event_id}",
    )
    db.add(row)
    return row


def seed_membership(
    db,
    *,
    email: str,
    tenant_id: str,
    role_name: str = "viewer",
    is_enabled: bool = True,
):
    db.add(
        models.TenantMembership(
            user_email=email,
            tenant_id=tenant_id,
            tenant_name=tenant_id.title(),
            role_name=role_name,
            is_enabled=is_enabled,
        )
    )


def seed_alert_dataset(
    *,
    membership_email: str | None = None,
    membership_tenant: str = "tenant-a",
    membership_enabled: bool = True,
    membership_role: str = "viewer",
):
    db = TestingSessionLocal()
    try:
        seed_inspection(db, 1, "tenant-a")
        seed_inspection(db, 2, "tenant-b")
        seed_alert_event(db, 101, 1, "tenant-a")
        seed_alert_event(db, 102, 2, "tenant-b")
        if membership_email:
            seed_membership(
                db,
                email=membership_email,
                tenant_id=membership_tenant,
                role_name=membership_role,
                is_enabled=membership_enabled,
            )
        db.commit()
    finally:
        db.close()


def item_ids(response):
    return sorted(item["inspection_id"] for item in response.json()["items"])


def test_global_admin_sees_all_alert_feed_and_open_rows():
    client = make_client()
    seed_alert_dataset()

    feed = client.get("/alerts/feed", headers=auth("dev-token"))
    open_alerts = client.get("/alerts/open", headers=auth("dev-token"))

    assert feed.status_code == 200
    assert open_alerts.status_code == 200
    assert item_ids(feed) == [1, 2]
    assert item_ids(open_alerts) == [1, 2]


def test_user_with_enabled_tenant_membership_sees_only_that_tenant_alert_rows():
    client = make_client()
    seed_alert_dataset(membership_email="viewer@local", membership_tenant="tenant-a")

    feed = client.get("/alerts/feed", headers=auth("viewer-token"))
    open_alerts = client.get("/alerts/open", headers=auth("viewer-token"))

    assert feed.status_code == 200
    assert open_alerts.status_code == 200
    assert item_ids(feed) == [1]
    assert item_ids(open_alerts) == [1]


def test_user_with_disabled_membership_sees_no_alert_rows():
    client = make_client()
    seed_alert_dataset(
        membership_email="viewer@local",
        membership_tenant="tenant-a",
        membership_enabled=False,
    )

    response = client.get("/alerts/feed", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_user_with_no_membership_sees_no_alert_rows():
    client = make_client()
    seed_alert_dataset()

    response = client.get("/alerts/feed", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_alerts_feed_is_no_longer_public():
    client = make_client()
    seed_alert_dataset()

    response = client.get("/alerts/feed")

    assert response.status_code == 401


def test_alerts_open_is_tenant_scoped():
    client = make_client()
    seed_alert_dataset(membership_email="vendor_user@local", membership_tenant="tenant-b")

    response = client.get("/alerts/open", headers=auth("vendor-token"))

    assert response.status_code == 200
    assert item_ids(response) == [2]


def test_acknowledge_denies_cross_tenant_access_with_403():
    client = make_client()
    seed_alert_dataset(membership_email="spd_manager@local", membership_tenant="tenant-a", membership_role="spd_manager")

    response = client.post(
        "/alerts/2/acknowledge",
        headers=auth("spd-manager-token"),
        json={"owner": "owner", "notes": "note"},
    )

    assert response.status_code == 403


def test_resolve_denies_cross_tenant_access_with_403():
    client = make_client()
    seed_alert_dataset(membership_email="spd_manager@local", membership_tenant="tenant-a", membership_role="spd_manager")

    response = client.post(
        "/alerts/2/resolve",
        headers=auth("spd-manager-token"),
        json={"owner": "owner", "notes": "note"},
    )

    assert response.status_code == 403


def test_send_alert_denies_cross_tenant_access_with_403():
    client = make_client()
    seed_alert_dataset(membership_email="spd_manager@local", membership_tenant="tenant-a", membership_role="spd_manager")

    response = client.post("/alerts/send/2", headers=auth("spd-manager-token"))

    assert response.status_code == 403


def test_resend_alert_event_denies_cross_tenant_access_with_403():
    client = make_client()
    seed_alert_dataset(membership_email="spd_manager@local", membership_tenant="tenant-a", membership_role="spd_manager")

    response = client.post("/alerts/resend/102", headers=auth("spd-manager-token"))

    assert response.status_code == 403


def test_alert_history_export_json_excludes_unauthorized_tenant_rows():
    client = make_client()
    seed_alert_dataset(membership_email="spd_manager@local", membership_tenant="tenant-a", membership_role="spd_manager")

    response = client.get("/alerts/history/export.json", headers=auth("spd-manager-token"))

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["inspection_id"] for item in items] == [1]
