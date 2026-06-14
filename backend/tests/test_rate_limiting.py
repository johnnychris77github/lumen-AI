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

from app.core.rate_limit import InMemoryRateLimiter, RateLimitMiddleware
from app.db import models


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reset_audit_table():
    models.AuditLog.__table__.drop(bind=engine, checkfirst=True)
    models.AuditLog.__table__.create(bind=engine)


def make_client(limits: dict[str, int] | None = None):
    reset_audit_table()
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        limiter=InMemoryRateLimiter(limits=limits or {"read": 2, "write": 1, "auth": 1, "export": 1}),
        db_session_factory=TestingSessionLocal,
    )

    @app.get("/api/alerts/feed")
    def alerts_feed():
        return {"ok": True}

    @app.post("/api/alerts/ack")
    def alerts_ack():
        return {"ok": True}

    @app.get("/api/audit-logs/export.json")
    def audit_export():
        return {"ok": True}

    @app.post("/api/auth/login")
    def auth_login():
        return {"ok": True}

    return TestClient(app)


def headers(tenant: str = "tenant-a", token: str = "user:one@example.test", ip: str = "203.0.113.10"):
    return {
        "X-Tenant-Id": tenant,
        "Authorization": f"Bearer {token}",
        "X-Forwarded-For": ip,
    }


def test_requests_below_threshold_succeed():
    client = make_client(limits={"read": 2})

    first = client.get("/api/alerts/feed", headers=headers())
    second = client.get("/api/alerts/feed", headers=headers())

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers["X-RateLimit-Remaining"] == "0"


def test_requests_exceeding_threshold_fail_with_429():
    client = make_client(limits={"read": 1})

    assert client.get("/api/alerts/feed", headers=headers()).status_code == 200
    response = client.get("/api/alerts/feed", headers=headers())

    assert response.status_code == 429


def test_limits_are_isolated_by_tenant():
    client = make_client(limits={"read": 1})

    assert client.get("/api/alerts/feed", headers=headers(tenant="tenant-a")).status_code == 200
    assert client.get("/api/alerts/feed", headers=headers(tenant="tenant-a")).status_code == 429
    assert client.get("/api/alerts/feed", headers=headers(tenant="tenant-b")).status_code == 200


def test_limits_are_isolated_by_user():
    client = make_client(limits={"read": 1})

    assert client.get("/api/alerts/feed", headers=headers(token="user:one@example.test")).status_code == 200
    assert client.get("/api/alerts/feed", headers=headers(token="user:one@example.test")).status_code == 429
    assert client.get("/api/alerts/feed", headers=headers(token="user:two@example.test")).status_code == 200


def test_retry_metadata_returned():
    client = make_client(limits={"export": 1})

    assert client.get("/api/audit-logs/export.json", headers=headers()).status_code == 200
    response = client.get("/api/audit-logs/export.json", headers=headers())

    assert response.status_code == 429
    body = response.json()
    assert body["retry_after_seconds"] > 0
    assert body["limit"] == 1
    assert body["remaining"] == 0
    assert response.headers["Retry-After"] == str(body["retry_after_seconds"])


def test_audit_event_created_for_violations():
    client = make_client(limits={"write": 1})

    assert client.post("/api/alerts/ack", headers=headers()).status_code == 200
    assert client.post("/api/alerts/ack", headers=headers()).status_code == 429

    db = TestingSessionLocal()
    try:
        row = db.query(models.AuditLog).one()
        assert row.tenant_id == "tenant-a"
        assert row.actor_email == "one@example.test"
        assert row.action_type == "rate_limit_exceeded"
        assert row.resource_type == "api_request"
        assert row.status == "blocked"
    finally:
        db.close()
