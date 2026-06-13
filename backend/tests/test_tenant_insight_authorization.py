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
from app.routes import tenant_insights as insight_routes


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

INSIGHTS = [
    {
        "tenant_id": 1,
        "tenant_name": "Tenant A",
        "health_status": "critical",
        "risk_level": "critical",
        "board_attention_required": True,
    },
    {
        "tenant_id": 2,
        "tenant_name": "Tenant B",
        "health_status": "healthy",
        "risk_level": "low",
        "board_attention_required": False,
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

    monkeypatch.setattr(insight_routes, "get_top_risk_tenant_insights", lambda db, limit=10: INSIGHTS[:limit])
    monkeypatch.setattr(
        insight_routes,
        "get_tenant_insight",
        lambda db, tenant_id: next((row for row in INSIGHTS if row["tenant_id"] == tenant_id), None),
    )
    monkeypatch.setattr(
        insight_routes,
        "portfolio_insight_rollup",
        lambda db: {"tenant_insight_count": len(INSIGHTS), "top_board_attention_items": [INSIGHTS[0]]},
    )

    app = FastAPI()
    app.include_router(insight_routes.router)
    app.dependency_overrides[insight_routes.get_db] = get_test_db
    return TestClient(app)


def test_tenant_insight_top_risks_are_tenant_scoped(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.get("/tenant-insights/top-risks", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert [row["tenant_id"] for row in response.json()] == [1]


def test_tenant_insight_rollup_is_tenant_scoped(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.get("/tenant-insights/rollup", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json()["tenant_insight_count"] == 1
    assert response.json()["board_attention_count"] == 1


def test_disabled_membership_has_empty_tenant_insight_scope(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1", is_enabled=False)

    response = client.get("/tenant-insights/top-risks", headers=auth("viewer-token"))

    assert response.status_code == 200
    assert response.json() == []


def test_tenant_insight_cross_tenant_lookup_returns_403(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.get("/tenant-insights/2", headers=auth("viewer-token"))

    assert response.status_code == 403


def test_missing_tenant_insight_returns_404(monkeypatch):
    client = make_client(monkeypatch)
    seed_membership(tenant_id="1")

    response = client.get("/tenant-insights/999", headers=auth("viewer-token"))

    assert response.status_code == 404
