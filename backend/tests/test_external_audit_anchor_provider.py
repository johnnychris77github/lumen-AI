from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.audit_anchor import AuditAnchorError, AuditAnchorSettings, create_audit_chain_anchor
from app.db import models

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class FakeResponse:
    status_code = 200
    headers = {"x-request-id": "request-123"}

    def __init__(self, payload=None):
        self.payload = payload or {"anchor_reference": "notary-ref-123", "sensitive": "ignored"}

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


def reset_db():
    models.AuditChainAnchor.__table__.drop(bind=engine, checkfirst=True)
    models.AuditLog.__table__.drop(bind=engine, checkfirst=True)
    models.AuditLog.__table__.create(bind=engine)
    models.AuditChainAnchor.__table__.create(bind=engine)


def seed_audit(db, tenant_id="tenant-a"):
    rows = [
        models.AuditLog(
            tenant_id=tenant_id,
            tenant_name=f"{tenant_id} name",
            actor_email="actor@example.test",
            actor_role="viewer",
            action_type="inspection_created",
            resource_type="inspection",
            resource_id="1",
            status="success",
            details='{"should_not_be_sent":"secret details"}',
        ),
        models.AuditLog(
            tenant_id=tenant_id,
            tenant_name=f"{tenant_id} name",
            actor_email="actor@example.test",
            actor_role="viewer",
            action_type="export_generated",
            resource_type="export",
            resource_id="2",
            status="success",
            details='{"more":"metadata"}',
        ),
    ]
    db.add_all(rows)
    db.commit()
    return rows


def fixed_time():
    return datetime(2026, 6, 12, 12, 0, 0, tzinfo=timezone.utc)


def test_internal_provider_still_works():
    reset_db()
    db = TestingSessionLocal()
    seed_audit(db)

    anchor = create_audit_chain_anchor(db, "tenant-a", timestamp=fixed_time())

    assert anchor.anchor_provider == "internal"
    assert anchor.anchor_reference == "internal"
    assert anchor.records_covered == 2
    assert len(anchor.anchor_hash) == 64
    db.close()


def test_external_provider_receives_only_safe_payload_and_stores_reference():
    reset_db()
    db = TestingSessionLocal()
    seed_audit(db)
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured.update({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResponse()

    settings = AuditAnchorSettings(
        provider="external_http",
        external_url="https://notary.example.test/anchors",
        external_token="top-secret-token",
        timeout_seconds=2.5,
    )

    anchor = create_audit_chain_anchor(db, "tenant-a", settings=settings, http_post=fake_post, timestamp=fixed_time())

    assert anchor.anchor_provider == "external_http"
    assert anchor.anchor_reference == "notary-ref-123"
    assert captured["json"] == {
        "anchor_hash": anchor.anchor_hash,
        "tenant_id": "tenant-a",
        "timestamp": fixed_time().isoformat(),
        "last_audit_log_id": 2,
        "records_covered": 2,
    }
    assert "details" not in str(captured["json"])
    assert "metadata" not in str(captured["json"])
    assert captured["headers"]["Authorization"] == "Bearer top-secret-token"
    assert "top-secret-token" not in anchor.anchor_reference
    db.close()


def test_external_failure_falls_back_when_configured():
    reset_db()
    db = TestingSessionLocal()
    seed_audit(db)

    def failing_post(*args, **kwargs):
        raise TimeoutError("network failed with top-secret-token")

    settings = AuditAnchorSettings(
        provider="external_http",
        external_url="https://notary.example.test/anchors",
        external_token="top-secret-token",
        fail_mode="internal_fallback",
    )

    anchor = create_audit_chain_anchor(db, "tenant-a", settings=settings, http_post=failing_post, timestamp=fixed_time())

    assert anchor.anchor_provider == "internal"
    assert anchor.anchor_reference == "internal_fallback"
    db.close()


def test_external_failure_blocks_when_fail_closed_and_token_not_leaked():
    reset_db()
    db = TestingSessionLocal()
    seed_audit(db)

    def failing_post(*args, **kwargs):
        raise TimeoutError("network failed with top-secret-token")

    settings = AuditAnchorSettings(
        provider="external_http",
        external_url="https://notary.example.test/anchors",
        external_token="top-secret-token",
        fail_mode="fail_closed",
    )

    with pytest.raises(AuditAnchorError) as exc:
        create_audit_chain_anchor(db, "tenant-a", settings=settings, http_post=failing_post, timestamp=fixed_time())

    assert "top-secret-token" not in str(exc.value)
    assert db.query(models.AuditChainAnchor).count() == 0
    db.close()


def test_external_response_body_is_not_stored():
    reset_db()
    db = TestingSessionLocal()
    seed_audit(db)

    def fake_post(*args, **kwargs):
        return FakeResponse({"anchor_reference": "safe-ref", "receipt": {"full": "do-not-store"}})

    settings = AuditAnchorSettings(provider="external_http", external_url="https://notary.example.test/anchors")

    anchor = create_audit_chain_anchor(db, "tenant-a", settings=settings, http_post=fake_post, timestamp=fixed_time())

    assert anchor.anchor_reference == "safe-ref"
    assert "do-not-store" not in anchor.anchor_reference
    db.close()
