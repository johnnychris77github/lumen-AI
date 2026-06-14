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
from app.routes import scim

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reset_tables():
    models.AuditLog.__table__.drop(bind=engine, checkfirst=True)
    models.TenantMembership.__table__.drop(bind=engine, checkfirst=True)
    models.User.__table__.drop(bind=engine, checkfirst=True)
    models.User.__table__.create(bind=engine)
    models.TenantMembership.__table__.create(bind=engine)
    models.AuditLog.__table__.create(bind=engine)


def make_client(*, enabled: bool = True, allowed_tenants: str = "tenant-a", token: str = "scim-secret"):
    reset_tables()
    os.environ["LUMENAI_SCIM_ENABLED"] = "true" if enabled else "false"
    os.environ["LUMENAI_SCIM_BEARER_TOKEN"] = token
    os.environ["LUMENAI_SCIM_ALLOWED_TENANTS"] = allowed_tenants
    os.environ["LUMENAI_SCIM_DEFAULT_ROLE"] = "viewer"
    os.environ["LUMENAI_SCIM_ALLOWED_ROLES"] = "viewer,reviewer,vendor_user"

    app = FastAPI()
    app.include_router(scim.router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[deps.get_db] = override_get_db
    app.dependency_overrides[scim.get_db] = override_get_db
    return TestClient(app)


def auth(token: str = "scim-secret"):
    return {"Authorization": f"Bearer {token}"}


def user_payload(email: str = "member@example.test", tenant_id: str = "tenant-a", role: str = "viewer", active: bool = True):
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": email,
        "active": active,
        "emails": [{"value": email, "primary": True}],
        "name": {"givenName": "Member", "familyName": "Example"},
        "urn:ietf:params:scim:schemas:extension:lumen:2.0:User": {
            "tenantId": tenant_id,
            "tenantName": f"{tenant_id} name",
            "role": role,
        },
    }


def db_rows():
    db = TestingSessionLocal()
    try:
        return db.query(models.TenantMembership).all(), db.query(models.AuditLog).all()
    finally:
        db.close()


def test_scim_disabled_returns_safe_failure():
    client = make_client(enabled=False)

    response = client.get("/scim/v2/Users", headers=auth())

    assert response.status_code == 404
    assert "scim-secret" not in response.text


def test_missing_invalid_and_dev_token_rejected_without_leakage():
    client = make_client()

    missing = client.get("/scim/v2/Users")
    invalid = client.get("/scim/v2/Users", headers=auth("wrong-token"))
    dev_token = client.get("/scim/v2/Users", headers=auth("dev-token"))

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert dev_token.status_code == 401
    assert "wrong-token" not in invalid.text
    assert "dev-token" not in dev_token.text


def test_user_create_provisions_tenant_membership_and_user_record():
    client = make_client()

    response = client.post("/scim/v2/Users", headers=auth(), json=user_payload(role="reviewer"))

    assert response.status_code == 201
    body = response.json()
    assert body["userName"] == "member@example.test"
    assert body["active"] is True
    assert body["urn:ietf:params:scim:schemas:extension:lumen:2.0:User"]["role"] == "reviewer"
    db = TestingSessionLocal()
    try:
        membership = db.query(models.TenantMembership).one()
        user = db.query(models.User).one()
        audit = db.query(models.AuditLog).one()
        assert membership.tenant_id == "tenant-a"
        assert membership.role_name == "reviewer"
        assert user.email == "member@example.test"
        assert audit.action_type == "scim_user_created"
    finally:
        db.close()


def test_user_update_changes_role_safely():
    client = make_client()
    created = client.post("/scim/v2/Users", headers=auth(), json=user_payload()).json()

    response = client.patch(
        f"/scim/v2/Users/{created['id']}",
        headers=auth(),
        json={"Operations": [{"op": "Replace", "path": "role", "value": "vendor_user"}]},
    )

    assert response.status_code == 200
    db = TestingSessionLocal()
    try:
        membership = db.query(models.TenantMembership).one()
        assert membership.role_name == "vendor_user"
        assert {row.action_type for row in db.query(models.AuditLog).all()} == {"scim_user_created", "scim_user_updated"}
    finally:
        db.close()


def test_user_delete_deactivates_membership_without_hard_delete():
    client = make_client()
    created = client.post("/scim/v2/Users", headers=auth(), json=user_payload()).json()

    response = client.delete(f"/scim/v2/Users/{created['id']}", headers=auth())

    assert response.status_code == 204
    db = TestingSessionLocal()
    try:
        membership = db.query(models.TenantMembership).one()
        assert membership.is_enabled is False
        assert db.query(models.User).count() == 1
        assert db.query(models.AuditLog).filter(models.AuditLog.action_type == "scim_user_deactivated").count() == 1
    finally:
        db.close()


def test_group_role_mapping_respects_allowed_roles():
    client = make_client()

    denied = client.post(
        "/scim/v2/Groups",
        headers=auth(),
        json={
            "displayName": "Tenant Admins",
            "members": [{"value": "group-member@example.test"}],
            "urn:ietf:params:scim:schemas:extension:lumen:2.0:Group": {
                "tenantId": "tenant-a",
                "tenantName": "Tenant A",
                "role": "admin",
            },
        },
    )
    allowed = client.post(
        "/scim/v2/Groups",
        headers=auth(),
        json={
            "displayName": "Tenant Reviewers",
            "members": [{"value": "group-member@example.test"}],
            "urn:ietf:params:scim:schemas:extension:lumen:2.0:Group": {
                "tenantId": "tenant-a",
                "tenantName": "Tenant A",
                "role": "reviewer",
            },
        },
    )

    assert denied.status_code == 403
    assert allowed.status_code == 201
    db = TestingSessionLocal()
    try:
        membership = db.query(models.TenantMembership).one()
        assert membership.role_name == "reviewer"
        assert db.query(models.AuditLog).filter(models.AuditLog.action_type == "scim_provisioning_denied").count() == 1
        assert db.query(models.AuditLog).filter(models.AuditLog.action_type == "scim_group_created").count() == 1
    finally:
        db.close()


def test_cross_tenant_provisioning_denied_and_audited():
    client = make_client(allowed_tenants="tenant-a")

    response = client.post("/scim/v2/Users", headers=auth(), json=user_payload(tenant_id="tenant-b"))

    assert response.status_code == 403
    assert "scim-secret" not in response.text
    db = TestingSessionLocal()
    try:
        assert db.query(models.TenantMembership).count() == 0
        audit = db.query(models.AuditLog).one()
        assert audit.action_type == "scim_provisioning_denied"
        assert audit.tenant_id == "tenant-b"
    finally:
        db.close()


def test_group_patch_updates_membership_and_list_endpoints_are_tenant_scoped():
    client = make_client(allowed_tenants="tenant-a")
    client.post("/scim/v2/Users", headers=auth(), json=user_payload("member@example.test", "tenant-a", "viewer"))

    response = client.patch(
        "/scim/v2/Groups/tenant-a:reviewer",
        headers=auth(),
        json={
            "members": [{"value": "member@example.test"}],
            "urn:ietf:params:scim:schemas:extension:lumen:2.0:Group": {
                "tenantId": "tenant-a",
                "tenantName": "Tenant A",
                "role": "reviewer",
            },
        },
    )
    users = client.get("/scim/v2/Users", headers=auth()).json()
    groups = client.get("/scim/v2/Groups", headers=auth()).json()

    assert response.status_code == 200
    assert users["totalResults"] == 1
    assert groups["totalResults"] == 1
    assert groups["Resources"][0]["urn:ietf:params:scim:schemas:extension:lumen:2.0:Group"]["tenantId"] == "tenant-a"
    db = TestingSessionLocal()
    try:
        membership = db.query(models.TenantMembership).one()
        assert membership.role_name == "reviewer"
        assert db.query(models.AuditLog).filter(models.AuditLog.action_type == "scim_group_updated").count() == 1
    finally:
        db.close()
