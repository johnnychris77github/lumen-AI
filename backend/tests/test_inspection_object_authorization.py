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

from app.db import models
from app.routes import inspections


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_client(current_user, memberships=None):
    models.TenantMembership.__table__.drop(bind=engine, checkfirst=True)
    models.Inspection.__table__.drop(bind=engine, checkfirst=True)
    models.Inspection.__table__.create(bind=engine)
    models.TenantMembership.__table__.create(bind=engine)

    db = TestingSessionLocal()
    row = models.Inspection(
        file_name="scope-test.jpg",
        tenant_id="tenant-a",
        tenant_name="Tenant A",
        status="completed",
        confidence=0.87,
        material_type="steel",
        vendor_name="Vendor One",
        site_name="Site One",
    )
    db.add(row)
    for membership in memberships or []:
        db.add(
            models.TenantMembership(
                user_email=membership["user_email"],
                tenant_id=membership["tenant_id"],
                tenant_name=membership.get("tenant_name", membership["tenant_id"]),
                role_name=membership.get("role_name", "viewer"),
                is_enabled=membership.get("is_enabled", True),
            )
        )
    db.commit()
    db.refresh(row)
    inspection_id = row.id
    db.close()

    app = FastAPI()
    app.include_router(inspections.router)

    def override_get_db():
        test_db = TestingSessionLocal()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[inspections.get_db] = override_get_db
    app.dependency_overrides[inspections.get_current_user] = lambda: current_user

    return TestClient(app), inspection_id


def user(role: str, email: str = "user@example.test", tenant_id: str | None = None):
    return SimpleNamespace(role=role, tenant_id=tenant_id, email=email)


def membership(
    user_email: str = "user@example.test",
    tenant_id: str = "tenant-a",
    is_enabled: bool = True,
):
    return {
        "user_email": user_email,
        "tenant_id": tenant_id,
        "tenant_name": f"{tenant_id} name",
        "is_enabled": is_enabled,
    }


def test_global_admin_can_read_any_inspection():
    client, inspection_id = make_client(user("admin", tenant_id="other-tenant"))

    response = client.get(f"/inspections/{inspection_id}")

    assert response.status_code == 200
    assert response.json()["id"] == inspection_id
    assert response.json()["tenant_id"] == "tenant-a"


def test_user_with_enabled_matching_tenant_membership_can_read_inspection():
    current_user = user("viewer", email="member@example.test")
    client, inspection_id = make_client(
        current_user,
        memberships=[membership(user_email=current_user.email, tenant_id="tenant-a")],
    )

    response = client.get(f"/inspections/{inspection_id}")

    assert response.status_code == 200
    assert response.json()["file_name"] == "scope-test.jpg"


def test_user_with_different_tenant_membership_receives_403():
    current_user = user("viewer", email="member@example.test", tenant_id="tenant-a")
    client, inspection_id = make_client(
        current_user,
        memberships=[membership(user_email=current_user.email, tenant_id="tenant-b")],
    )

    response = client.get(f"/inspections/{inspection_id}")

    assert response.status_code == 403


def test_user_with_disabled_matching_tenant_membership_receives_403():
    current_user = user("viewer", email="member@example.test", tenant_id="tenant-a")
    client, inspection_id = make_client(
        current_user,
        memberships=[
            membership(
                user_email=current_user.email,
                tenant_id="tenant-a",
                is_enabled=False,
            )
        ],
    )

    response = client.get(f"/inspections/{inspection_id}")

    assert response.status_code == 403


def test_user_with_no_tenant_membership_receives_403():
    client, inspection_id = make_client(user("viewer", tenant_id="tenant-a"))

    response = client.get(f"/inspections/{inspection_id}")

    assert response.status_code == 403


def test_missing_inspection_receives_404():
    client, inspection_id = make_client(user("admin"))

    response = client.get(f"/inspections/{inspection_id + 1}")

    assert response.status_code == 404
