from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.rate_limit import RateLimitSettings, enforce_rate_limit, reset_rate_limit_state
from app.core.rate_limit_store import InMemoryRateLimitStore, RateLimitStoreError, RedisRateLimitStore
from app.db import models


class FakeRedis:
    def __init__(self, fail: bool = False):
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.fail = fail

    def _maybe_fail(self):
        if self.fail:
            raise TimeoutError("redis timeout")

    def incr(self, key: str):
        self._maybe_fail()
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def expire(self, key: str, ttl: int):
        self._maybe_fail()
        self.ttls[key] = ttl
        return True

    def get(self, key: str):
        self._maybe_fail()
        return self.values.get(key)

    def delete(self, key: str):
        self._maybe_fail()
        self.values.pop(key, None)
        self.ttls.pop(key, None)
        return 1

    def ttl(self, key: str):
        self._maybe_fail()
        return self.ttls.get(key, -2)


def user(email: str = "user@example.test", role: str = "viewer", tenant_id: str | None = None):
    return SimpleNamespace(email=email, role=role, tenant_id=tenant_id)


def settings(limit: int = 2, backend: str = "in_memory", fail_mode: str = "fallback"):
    return RateLimitSettings(
        backend=backend,
        fail_mode=fail_mode,
        window_seconds=60,
        limits={"read": limit, "write": limit, "export": limit, "auth": limit, "authentication": limit, "abuse": limit},
    )


def test_in_memory_backend_still_works():
    reset_rate_limit_state()
    store = InMemoryRateLimitStore()
    current_user = user("reader@example.test")
    config = settings(limit=2)

    first = enforce_rate_limit(category="read", tenant_id="tenant-a", current_user=current_user, settings=config, store=store)
    second = enforce_rate_limit(category="read", tenant_id="tenant-a", current_user=current_user, settings=config, store=store)

    assert first.remaining == 1
    assert second.remaining == 0
    with pytest.raises(HTTPException) as exc:
        enforce_rate_limit(category="read", tenant_id="tenant-a", current_user=current_user, settings=config, store=store)
    assert exc.value.status_code == 429
    assert exc.value.detail["limit"] == 2
    assert exc.value.detail["remaining"] == 0


def test_redis_backend_works_with_mocked_client():
    fake = FakeRedis()
    store = RedisRateLimitStore("redis://test", client=fake, prefix="test")
    current_user = user("reader@example.test")
    config = settings(limit=2, backend="redis")

    decision = enforce_rate_limit(category="read", tenant_id="tenant-a", current_user=current_user, settings=config, store=store)

    assert decision.backend == "redis"
    assert decision.remaining == 1
    assert fake.values["test:rate_limit:read:tenant:tenant-a:user:reader@example.test:ip:unknown-ip"] == 1


def test_redis_counters_are_shared_across_simulated_workers():
    fake = FakeRedis()
    worker_one = RedisRateLimitStore("redis://test", client=fake, prefix="test")
    worker_two = RedisRateLimitStore("redis://test", client=fake, prefix="test")
    current_user = user("shared@example.test")
    config = settings(limit=1, backend="redis")

    enforce_rate_limit(category="write", tenant_id="tenant-a", current_user=current_user, settings=config, store=worker_one)

    with pytest.raises(HTTPException) as exc:
        enforce_rate_limit(category="write", tenant_id="tenant-a", current_user=current_user, settings=config, store=worker_two)
    assert exc.value.status_code == 429


def test_redis_timeout_falls_back_to_in_memory_when_configured():
    redis_store = RedisRateLimitStore("redis://test", client=FakeRedis(fail=True), prefix="test")
    fallback_store = InMemoryRateLimitStore()
    current_user = user("fallback@example.test")
    config = settings(limit=1, backend="redis", fail_mode="fallback")

    decision = enforce_rate_limit(
        category="read",
        tenant_id="tenant-a",
        current_user=current_user,
        settings=config,
        store=redis_store,
        fallback_store=fallback_store,
    )

    assert decision.allowed is True
    assert decision.backend == "in_memory"


def test_redis_timeout_fail_closed_returns_429():
    redis_store = RedisRateLimitStore("redis://test", client=FakeRedis(fail=True), prefix="test")
    current_user = user("blocked@example.test")
    config = settings(limit=1, backend="redis", fail_mode="fail_closed")

    with pytest.raises(HTTPException) as exc:
        enforce_rate_limit(
            category="read",
            tenant_id="tenant-a",
            current_user=current_user,
            settings=config,
            store=redis_store,
        )

    assert exc.value.status_code == 429
    assert exc.value.detail["limit"] == 1
    assert exc.value.detail["remaining"] == 0


def test_store_timeout_is_wrapped_safely():
    redis_store = RedisRateLimitStore("redis://test", client=FakeRedis(fail=True), prefix="test")

    with pytest.raises(RateLimitStoreError):
        redis_store.increment_counter("key", 60)


def test_audit_event_created_when_rate_limit_exceeded():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.AuditLog.__table__.drop(bind=engine, checkfirst=True)
    models.AuditLog.__table__.create(bind=engine)
    db = TestingSessionLocal()
    store = InMemoryRateLimitStore()
    current_user = user("audit@example.test", "viewer")
    config = settings(limit=1)

    enforce_rate_limit(category="export", tenant_id="tenant-a", current_user=current_user, settings=config, store=store, db=db)
    with pytest.raises(HTTPException):
        enforce_rate_limit(category="export", tenant_id="tenant-a", current_user=current_user, settings=config, store=store, db=db)

    rows = db.query(models.AuditLog).all()
    db.close()
    assert len(rows) == 1
    assert rows[0].action_type == "rate_limit_exceeded"
    assert rows[0].tenant_id == "tenant-a"
    assert rows[0].actor_email == "audit@example.test"


@pytest.mark.parametrize(
    ("category", "expected_action"),
    [
        ("auth", "auth_throttled"),
        ("abuse", "abuse_detection"),
    ],
)
def test_named_audit_events_created_for_auth_and_abuse_limits(category, expected_action):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.AuditLog.__table__.drop(bind=engine, checkfirst=True)
    models.AuditLog.__table__.create(bind=engine)
    db = TestingSessionLocal()
    store = InMemoryRateLimitStore()
    config = settings(limit=1)

    enforce_rate_limit(category=category, tenant_id="tenant-a", current_user=None, settings=config, store=store, db=db)
    with pytest.raises(HTTPException):
        enforce_rate_limit(category=category, tenant_id="tenant-a", current_user=None, settings=config, store=store, db=db)

    rows = db.query(models.AuditLog).all()
    db.close()
    assert len(rows) == 1
    assert rows[0].action_type == expected_action


def test_tenant_isolation_preserved():
    store = InMemoryRateLimitStore()
    current_user = user("tenant-member@example.test")
    config = settings(limit=1)

    enforce_rate_limit(category="read", tenant_id="tenant-a", current_user=current_user, settings=config, store=store)
    enforce_rate_limit(category="read", tenant_id="tenant-b", current_user=current_user, settings=config, store=store)

    with pytest.raises(HTTPException):
        enforce_rate_limit(category="read", tenant_id="tenant-a", current_user=current_user, settings=config, store=store)


def test_user_isolation_preserved():
    store = InMemoryRateLimitStore()
    config = settings(limit=1)

    enforce_rate_limit(category="read", tenant_id="tenant-a", current_user=user("one@example.test"), settings=config, store=store)
    enforce_rate_limit(category="read", tenant_id="tenant-a", current_user=user("two@example.test"), settings=config, store=store)

    with pytest.raises(HTTPException):
        enforce_rate_limit(category="read", tenant_id="tenant-a", current_user=user("one@example.test"), settings=config, store=store)
