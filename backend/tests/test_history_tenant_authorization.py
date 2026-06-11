from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import deps
from app.db import models
from app.routes import history


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def user(role: str, email: str = "user@example.test", tenant_id: str | None = None):
    return SimpleNamespace(role=role, email=email, tenant_id=tenant_id)


def membership(
    user_email: str = "user@example.test",
    tenant_id: str = "tenant-a",
    is_enabled: bool = True,
):
    return models.TenantMembership(
        user_email=user_email,
        tenant_id=tenant_id,
        tenant_name=f"{tenant_id} name",
        role_name="viewer",
        is_enabled=is_enabled,
    )


def make_inspection(tenant_id: str, file_name: str, status: str = "completed"):
    return models.Inspection(
        file_name=file_name,
        tenant_id=tenant_id,
        tenant_name=f"{tenant_id} name",
        status=status,
        confidence=0.91,
        material_type="steel",
        vendor_name="Vendor One",
        site_name="Site One",
    )


def make_client(current_user, memberships=None):
    models.TenantMembership.__table__.drop(bind=engine, checkfirst=True)
    models.Inspection.__table__.drop(bind=engine, checkfirst=True)
    models.Inspection.__table__.create(bind=engine)
    models.TenantMembership.__table__.create(bind=engine)

    db = TestingSessionLocal()
    db.add_all(
        [
            make_inspection("tenant-a", "tenant-a-1.jpg", "completed"),
            make_inspection("tenant-a", "tenant-a-2.jpg", "queued"),
            make_inspection("tenant-b", "tenant-b-1.jpg", "failed"),
        ]
    )
    db.add_all(memberships or [])
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(history.router)

    def override_get_db():
        test_db = TestingSessionLocal()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[history.get_db] = override_get_db
    app.dependency_overrides[deps.get_current_user] = lambda: current_user

    return TestClient(app)


def history_items(response):
    assert response.status_code == 200
    return response.json()["items"]


def test_admin_sees_all_tenant_inspections():
    client = make_client(user("admin", "admin@example.test"))

    items = history_items(client.get("/history"))

    assert {item["tenant_id"] for item in items} == {"tenant-a", "tenant-b"}
    assert len(items) == 3


def test_user_with_one_enabled_tenant_membership_sees_only_that_tenant():
    current_user = user("viewer", "member@example.test", tenant_id="tenant-b")
    client = make_client(
        current_user,
        memberships=[membership(current_user.email, "tenant-a")],
    )

    items = history_items(client.get("/history"))

    assert [item["tenant_id"] for item in items] == ["tenant-a", "tenant-a"]
    assert {item["file_name"] for item in items} == {"tenant-a-1.jpg", "tenant-a-2.jpg"}


def test_user_with_disabled_membership_sees_no_rows():
    current_user = user("viewer", "member@example.test")
    client = make_client(
        current_user,
        memberships=[membership(current_user.email, "tenant-a", is_enabled=False)],
    )

    assert history_items(client.get("/history")) == []


def test_user_with_no_membership_sees_no_rows():
    client = make_client(user("viewer", "member@example.test", tenant_id="tenant-a"))

    assert history_items(client.get("/history")) == []


def test_history_summary_counts_only_authorized_rows():
    current_user = user("viewer", "member@example.test")
    client = make_client(
        current_user,
        memberships=[membership(current_user.email, "tenant-a")],
    )

    response = client.get("/history/summary")

    assert response.status_code == 200
    assert response.json()["total_inspections"] == 2
    assert response.json()["completed"] == 1
    assert response.json()["queued"] == 1
    assert response.json()["failed"] == 0


def test_export_json_does_not_include_unauthorized_tenant_rows():
    current_user = user("vendor_user", "member@example.test")
    client = make_client(
        current_user,
        memberships=[membership(current_user.email, "tenant-a")],
    )

    items = history_items(client.get("/history/export.json"))

    assert {item["tenant_id"] for item in items} == {"tenant-a"}
    assert "tenant-b-1.jpg" not in {item["file_name"] for item in items}
