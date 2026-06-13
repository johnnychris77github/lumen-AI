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
from app.routes import portfolio_tenants as portfolio_routes


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TENANTS = [
    {
        "id": 1,
        "tenant_name": "Tenant A",
        "health_status": "critical",
        "health_score": 25,
        "governance_exception_count": 3,
        "next_qbr_date": None,
    },
    {
        "id": 2,
        "tenant_name": "Tenant B",
        "health_status": "healthy",
        "health_score": 90,
        "governance_exception_count": 0,
        "next_qbr_date": None,
    },
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


def seed_membership(*, email: str = "viewer@local", tenant_id: str = "1", is_enabled: bool = True):
    db = TestingSessionLocal()
    try:
        db.add(
            models.TenantMembership(
                user_email=email,
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

    monkeypatch.setattr(portfolio_routes, "list_portfolio_tenants", lambda db, limit=100: TENANTS[:limit])
    monkeypatch.setattr(
        portfolio_routes,
        "get_portfolio_tenant",
        lambda db, tenant_id: next((row for row in TENANTS if row["id"] == tenant_id), None),
    )
    monkeypatch.setattr(
        portfolio_routes,
        "update_portfolio_tenant",
        lambda db, tenant_id, updates: {
            **next(row for row in TENANTS if row["id"] == tenant_id),
            **updates,
        },
    )
    monkeypatch.setattr(portfolio_routes, "create_portfolio_tenant", lambda **kwargs: {"id": 3, **kwargs})
    monkeypatch.setattr(portfolio_routes, "rescore_portfolio_tenants", lambda db: TENANTS)
    monkeypatch.setattr(portfolio_routes, "generate_board_briefing_from_portfolio_tenants", lambda **kwargs: {"id": 1})

    app = FastAPI()
    app.include_router(portfolio_routes.router)
    app.dependency_overrides[portfolio_routes.get_db] = get_test_db
    return TestClient(app)


def test_admin_can_list_all_portfolio_tenants(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get("/portfolio-tenants", headers=auth("dev-token"))

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [1, 2]


def test_non_admin_with_enabled_membership_sees_only_that_tenant(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.get("/portfolio-tenants", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [1]


def test_non_admin_with_disabled_membership_sees_no_tenant_rows(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1", is_enabled=False)

    response = client.get("/portfolio-tenants", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json() == []


def test_non_admin_with_no_membership_sees_no_tenant_rows(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get("/portfolio-tenants", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json() == []


def test_non_admin_cannot_get_another_tenant(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.get("/portfolio-tenants/2", headers=auth("viewer-token"))

    assert response.status_code == 403


def test_non_admin_cannot_patch_another_tenant(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.patch(
        "/portfolio-tenants/2",
        json={"notes": "changed"},
        headers=auth("viewer-token"),
    )

    assert response.status_code == 403


def test_non_admin_cannot_create_portfolio_tenant(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.post(
        "/portfolio-tenants",
        json={"tenant_name": "Tenant C"},
        headers=auth("viewer-token"),
    )

    assert response.status_code == 403


def test_non_admin_cannot_rescore_all_tenants(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.post("/portfolio-tenants/rescore", headers=auth("viewer-token"))

    assert response.status_code == 403


def test_non_admin_cannot_generate_global_board_briefing(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.post(
        "/portfolio-tenants/generate-board-briefing",
        json={"period_label": "Q2"},
        headers=auth("viewer-token"),
    )

    assert response.status_code == 403
