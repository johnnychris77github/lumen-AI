from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Iterable

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

DEFAULT_LIMITS = {
    "read": 300,
    "write": 100,
    "auth": 20,
    "export": 25,
}
WINDOW_SECONDS = 60 * 60

PROTECTED_PREFIXES = (
    "/api/alerts",
    "/api/history",
    "/api/inspections",
    "/api/stream",
    "/api/reports",
    "/api/audit-logs",
    "/api/compliance-exports",
    "/api/trust-center-exports",
    "/api/leadership-packets",
    "/api/enterprise",
    "/api/enterprise-audit-events",
    "/api/enterprise-access",
)
AUTH_PREFIXES = ("/api/auth", "/auth")
EXPORT_MARKERS = ("export", ".pdf", ".csv", ".xlsx", ".zip", "evidence-pack")
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int
    limit: int
    remaining: int
    category: str
    key: tuple[str, str, str, str]


class InMemoryRateLimiter:
    def __init__(
        self,
        *,
        limits: dict[str, int] | None = None,
        window_seconds: int = WINDOW_SECONDS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.limits = {**DEFAULT_LIMITS, **(limits or {})}
        self.window_seconds = window_seconds
        self.clock = clock or time.time
        self._events: dict[tuple[str, str, str, str], deque[float]] = defaultdict(deque)

    def check(self, *, category: str, tenant_id: str, user_id: str, ip_address: str) -> RateLimitDecision:
        limit = self.limits.get(category, self.limits["read"])
        now = self.clock()
        key = (category, tenant_id or "default-tenant", user_id or "anonymous", ip_address or "unknown")
        events = self._events[key]
        cutoff = now - self.window_seconds

        while events and events[0] <= cutoff:
            events.popleft()

        if len(events) >= limit:
            retry_after = max(1, int(self.window_seconds - (now - events[0])))
            return RateLimitDecision(
                allowed=False,
                retry_after_seconds=retry_after,
                limit=limit,
                remaining=0,
                category=category,
                key=key,
            )

        events.append(now)
        return RateLimitDecision(
            allowed=True,
            retry_after_seconds=0,
            limit=limit,
            remaining=max(limit - len(events), 0),
            category=category,
            key=key,
        )


def _matches(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def is_protected_path(path: str) -> bool:
    return _matches(path, PROTECTED_PREFIXES) or _matches(path, AUTH_PREFIXES)


def classify_request(method: str, path: str) -> str:
    lower_path = path.lower()
    if _matches(lower_path, AUTH_PREFIXES):
        return "auth"
    if any(marker in lower_path for marker in EXPORT_MARKERS):
        return "export"
    if method.upper() in WRITE_METHODS:
        return "write"
    return "read"


def tenant_id_from_request(request: Request) -> str:
    return (request.headers.get("x-tenant-id") or "default-tenant").strip() or "default-tenant"


def user_id_from_request(request: Request) -> str:
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token.startswith("user:"):
            return token.split("user:", 1)[1].strip().lower() or "anonymous"
        return token or "anonymous"
    return "anonymous"


def ip_address_from_request(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded_for:
        return forwarded_for
    return request.client.host if request.client else "unknown"


def rate_limit_exceeded_response(decision: RateLimitDecision) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests",
            "retry_after_seconds": decision.retry_after_seconds,
            "limit": decision.limit,
            "remaining": decision.remaining,
        },
        headers={"Retry-After": str(decision.retry_after_seconds)},
    )


def audit_rate_limit_violation(
    request: Request,
    decision: RateLimitDecision,
    *,
    db_session_factory: Callable[[], Session] | None = None,
) -> None:
    try:
        if db_session_factory is None:
            from app.db import SessionLocal

            db_session_factory = SessionLocal
        from app.audit import log_audit_event

        db = db_session_factory()
        try:
            _category, tenant_id, user_id, ip_address = decision.key
            log_audit_event(
                db,
                tenant_id=tenant_id,
                tenant_name=request.headers.get("x-tenant-name") or tenant_id,
                actor_email=user_id,
                actor_role="unknown",
                action_type="rate_limit_exceeded",
                resource_type="api_request",
                resource_id=f"{request.method} {request.url.path}",
                status="blocked",
                request=request,
                details={
                    "category": decision.category,
                    "limit": decision.limit,
                    "remaining": decision.remaining,
                    "retry_after_seconds": decision.retry_after_seconds,
                    "ip_address": ip_address,
                },
                compliance_flag=True,
            )
        finally:
            db.close()
    except Exception:
        # Rate-limit enforcement must not fail open because audit persistence is unavailable.
        return


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        limiter: InMemoryRateLimiter | None = None,
        limits: dict[str, int] | None = None,
        protected_prefixes: tuple[str, ...] = PROTECTED_PREFIXES,
        db_session_factory: Callable[[], Session] | None = None,
    ) -> None:
        super().__init__(app)
        self.limiter = limiter or InMemoryRateLimiter(limits=limits)
        self.protected_prefixes = protected_prefixes
        self.db_session_factory = db_session_factory

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not (_matches(path, self.protected_prefixes) or _matches(path, AUTH_PREFIXES)):
            return await call_next(request)

        decision = self.limiter.check(
            category=classify_request(request.method, path),
            tenant_id=tenant_id_from_request(request),
            user_id=user_id_from_request(request),
            ip_address=ip_address_from_request(request),
        )
        if not decision.allowed:
            audit_rate_limit_violation(
                request,
                decision,
                db_session_factory=self.db_session_factory,
            )
            return rate_limit_exceeded_response(decision)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        return response


def rate_limited(limiter: InMemoryRateLimiter | None = None):
    local_limiter = limiter or InMemoryRateLimiter()

    async def dependency(request: Request):
        decision = local_limiter.check(
            category=classify_request(request.method, request.url.path),
            tenant_id=tenant_id_from_request(request),
            user_id=user_id_from_request(request),
            ip_address=ip_address_from_request(request),
        )
        if not decision.allowed:
            audit_rate_limit_violation(request, decision)
            raise HTTPException(
                status_code=429,
                detail={
                    "retry_after_seconds": decision.retry_after_seconds,
                    "limit": decision.limit,
                    "remaining": decision.remaining,
                },
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )
        return decision

    return Depends(dependency)
