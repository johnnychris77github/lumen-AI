from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit import log_audit_event
from app.deps import get_current_user, get_db

from .rate_limit_store import InMemoryRateLimitStore, RateLimitStore, RateLimitStoreError, RedisRateLimitStore

READ_LIMIT = 300
WRITE_LIMIT = 100
AUTH_LIMIT = 20
EXPORT_LIMIT = 25
DEFAULT_WINDOW_SECONDS = 60 * 60

RATE_LIMIT_ACTIONS = {
    "auth": "auth_throttled",
    "authentication": "auth_throttled",
    "abuse": "abuse_detection",
}

GLOBAL_IN_MEMORY_STORE = InMemoryRateLimitStore()
_REDIS_STORE: RedisRateLimitStore | None = None


@dataclass(frozen=True)
class RateLimitSettings:
    backend: str = "in_memory"
    redis_url: str = "redis://localhost:6379/0"
    redis_prefix: str = "lumenai"
    redis_timeout_seconds: float = 1.0
    fail_mode: str = "fallback"
    window_seconds: int = DEFAULT_WINDOW_SECONDS
    limits: dict[str, int] = field(
        default_factory=lambda: {
            "read": READ_LIMIT,
            "write": WRITE_LIMIT,
            "auth": AUTH_LIMIT,
            "authentication": AUTH_LIMIT,
            "abuse": WRITE_LIMIT,
            "export": EXPORT_LIMIT,
        }
    )

    @classmethod
    def from_env(cls) -> "RateLimitSettings":
        return cls(
            backend=os.getenv("LUMENAI_RATE_LIMIT_BACKEND", "in_memory").strip().lower() or "in_memory",
            redis_url=os.getenv("LUMENAI_REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0")),
            redis_prefix=os.getenv("LUMENAI_REDIS_PREFIX", "lumenai"),
            redis_timeout_seconds=float(os.getenv("LUMENAI_REDIS_TIMEOUT_SECONDS", "1.0")),
            fail_mode=os.getenv("LUMENAI_RATE_LIMIT_FAIL_MODE", "fallback").strip().lower() or "fallback",
        )

    def limit_for(self, category: str) -> int:
        return self.limits.get(category, READ_LIMIT)


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int
    count: int
    key: str
    backend: str

    def response_detail(self) -> dict[str, int]:
        return {
            "retry_after_seconds": self.retry_after_seconds,
            "limit": self.limit,
            "remaining": self.remaining,
        }


def reset_rate_limit_state() -> None:
    GLOBAL_IN_MEMORY_STORE.reset_all()
    global _REDIS_STORE
    _REDIS_STORE = None


def _configured_store(settings: RateLimitSettings) -> RateLimitStore:
    if settings.backend == "redis":
        global _REDIS_STORE
        if _REDIS_STORE is None:
            _REDIS_STORE = RedisRateLimitStore(
                settings.redis_url,
                prefix=settings.redis_prefix,
                timeout_seconds=settings.redis_timeout_seconds,
            )
        return _REDIS_STORE
    return GLOBAL_IN_MEMORY_STORE


def _client_ip(request: Request | None) -> str:
    if request is None:
        return "unknown-ip"
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded_for:
        return forwarded_for
    if request.client and request.client.host:
        return request.client.host
    return "unknown-ip"


def _actor_email(current_user: Any | None) -> str:
    return (
        getattr(current_user, "email", "")
        or getattr(current_user, "user_email", "")
        or (current_user.get("email") if isinstance(current_user, dict) else "")
        or (current_user.get("user_email") if isinstance(current_user, dict) else "")
        or "anonymous"
    ).strip().lower()


def _actor_role(current_user: Any | None) -> str:
    return (
        getattr(current_user, "role", "")
        or getattr(current_user, "role_name", "")
        or (current_user.get("role") if isinstance(current_user, dict) else "")
        or (current_user.get("role_name") if isinstance(current_user, dict) else "")
        or "anonymous"
    )


def _rate_limit_key(
    *,
    category: str,
    tenant_id: str | None,
    current_user: Any | None,
    request: Request | None,
) -> str:
    tenant_part = str(tenant_id or getattr(current_user, "tenant_id", None) or "global").strip()
    user_part = _actor_email(current_user)
    ip_part = _client_ip(request)
    return f"{category}:tenant:{tenant_part}:user:{user_part}:ip:{ip_part}"


def _audit_limit_event(
    *,
    db: Session | None,
    request: Request | None,
    current_user: Any | None,
    tenant_id: str | None,
    category: str,
    decision: RateLimitDecision | None,
    store_error: str | None = None,
) -> None:
    if db is None:
        return

    action_type = RATE_LIMIT_ACTIONS.get(category, "rate_limit_exceeded")
    try:
        log_audit_event(
            db,
            tenant_id=tenant_id or "default-tenant",
            tenant_name=tenant_id or "Default Tenant",
            actor_email=_actor_email(current_user),
            actor_role=_actor_role(current_user),
            action_type=action_type,
            resource_type="rate_limit",
            resource_id=decision.key if decision else category,
            status="denied",
            request=request,
            details={
                "category": category,
                "limit": decision.limit if decision else None,
                "remaining": decision.remaining if decision else 0,
                "retry_after_seconds": decision.retry_after_seconds if decision else None,
                "store_error": store_error,
            },
            compliance_flag=True,
        )
    except Exception:
        # Rate limiting must never leak or fail because audit persistence failed.
        return


def evaluate_rate_limit(
    *,
    category: str = "read",
    tenant_id: str | None = None,
    current_user: Any | None = None,
    request: Request | None = None,
    settings: RateLimitSettings | None = None,
    store: RateLimitStore | None = None,
    fallback_store: RateLimitStore | None = None,
) -> RateLimitDecision:
    settings = settings or RateLimitSettings.from_env()
    category = (category or "read").strip().lower()
    limit = settings.limit_for(category)
    key = _rate_limit_key(category=category, tenant_id=tenant_id, current_user=current_user, request=request)
    selected_store = store or _configured_store(settings)
    backend = settings.backend

    try:
        count = selected_store.increment_counter(key, settings.window_seconds)
        retry_after = selected_store.get_ttl(key)
    except RateLimitStoreError:
        if settings.backend == "redis" and settings.fail_mode == "fallback":
            selected_store = fallback_store or GLOBAL_IN_MEMORY_STORE
            backend = "in_memory"
            count = selected_store.increment_counter(key, settings.window_seconds)
            retry_after = selected_store.get_ttl(key)
        else:
            return RateLimitDecision(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after_seconds=settings.window_seconds,
                count=limit + 1,
                key=key,
                backend=backend,
            )

    remaining = max(0, limit - count)
    return RateLimitDecision(
        allowed=count <= limit,
        limit=limit,
        remaining=remaining,
        retry_after_seconds=retry_after,
        count=count,
        key=key,
        backend=backend,
    )


def enforce_rate_limit(
    *,
    category: str = "read",
    tenant_id: str | None = None,
    current_user: Any | None = None,
    request: Request | None = None,
    db: Session | None = None,
    settings: RateLimitSettings | None = None,
    store: RateLimitStore | None = None,
    fallback_store: RateLimitStore | None = None,
) -> RateLimitDecision:
    decision = evaluate_rate_limit(
        category=category,
        tenant_id=tenant_id,
        current_user=current_user,
        request=request,
        settings=settings,
        store=store,
        fallback_store=fallback_store,
    )
    if decision.allowed:
        return decision

    _audit_limit_event(
        db=db,
        request=request,
        current_user=current_user,
        tenant_id=tenant_id,
        category=category,
        decision=decision,
        store_error="redis_unavailable" if decision.count > decision.limit and decision.backend == "redis" else None,
    )
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=decision.response_detail(),
    )


def rate_limit_dependency(category: str = "read", tenant_id_getter: Callable[[Request, Any], str | None] | None = None):
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Any = Depends(get_current_user),
    ) -> RateLimitDecision:
        tenant_id = tenant_id_getter(request, current_user) if tenant_id_getter else None
        return enforce_rate_limit(
            category=category,
            tenant_id=tenant_id,
            current_user=current_user,
            request=request,
            db=db,
        )

    return dependency


def read_rate_limit():
    return rate_limit_dependency("read")


def write_rate_limit():
    return rate_limit_dependency("write")


def export_rate_limit():
    return rate_limit_dependency("export")


def auth_rate_limit():
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
    ) -> RateLimitDecision:
        return enforce_rate_limit(
            category="auth",
            request=request,
            db=db,
        )

    return dependency
