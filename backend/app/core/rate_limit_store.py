from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol


class RateLimitStoreError(RuntimeError):
    """Raised when the configured rate limit backing store is unavailable."""


class RateLimitStore(Protocol):
    def increment_counter(self, key: str, window_seconds: int) -> int:
        ...

    def get_counter(self, key: str) -> int:
        ...

    def reset_counter(self, key: str) -> None:
        ...

    def get_ttl(self, key: str) -> int:
        ...


@dataclass
class InMemoryRateLimitStore:
    _counters: dict[str, tuple[int, float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _prune_expired(self, now: float | None = None) -> None:
        current_time = now if now is not None else time.time()
        expired = [key for key, (_, expires_at) in self._counters.items() if expires_at <= current_time]
        for key in expired:
            self._counters.pop(key, None)

    def increment_counter(self, key: str, window_seconds: int) -> int:
        now = time.time()
        with self._lock:
            self._prune_expired(now)
            count, expires_at = self._counters.get(key, (0, now + window_seconds))
            if expires_at <= now:
                count = 0
                expires_at = now + window_seconds
            count += 1
            self._counters[key] = (count, expires_at)
            return count

    def get_counter(self, key: str) -> int:
        now = time.time()
        with self._lock:
            self._prune_expired(now)
            return self._counters.get(key, (0, now))[0]

    def reset_counter(self, key: str) -> None:
        with self._lock:
            self._counters.pop(key, None)

    def get_ttl(self, key: str) -> int:
        now = time.time()
        with self._lock:
            self._prune_expired(now)
            if key not in self._counters:
                return 0
            return max(0, int(self._counters[key][1] - now))

    def reset_all(self) -> None:
        with self._lock:
            self._counters.clear()


class RedisRateLimitStore:
    def __init__(
        self,
        redis_url: str,
        *,
        prefix: str = "lumenai",
        timeout_seconds: float = 1.0,
        client: Any | None = None,
    ) -> None:
        self.redis_url = redis_url
        self.prefix = (prefix or "lumenai").strip(":")
        self.timeout_seconds = timeout_seconds
        self.client = client if client is not None else self._create_client(redis_url, timeout_seconds)

    @staticmethod
    def _create_client(redis_url: str, timeout_seconds: float):
        try:
            from redis import Redis
        except ImportError as exc:  # pragma: no cover - dependency is present in normal deployments
            raise RateLimitStoreError("Redis client dependency is unavailable") from exc

        return Redis.from_url(
            redis_url,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            decode_responses=True,
        )

    def _key(self, key: str) -> str:
        return f"{self.prefix}:rate_limit:{key}"

    def increment_counter(self, key: str, window_seconds: int) -> int:
        redis_key = self._key(key)
        try:
            value = int(self.client.incr(redis_key))
            if value == 1:
                self.client.expire(redis_key, int(window_seconds))
            return value
        except Exception as exc:  # noqa: BLE001 - Redis clients raise several connection/timeout classes
            raise RateLimitStoreError("Redis rate limit store unavailable") from exc

    def get_counter(self, key: str) -> int:
        try:
            value = self.client.get(self._key(key))
            return int(value or 0)
        except Exception as exc:  # noqa: BLE001
            raise RateLimitStoreError("Redis rate limit store unavailable") from exc

    def reset_counter(self, key: str) -> None:
        try:
            self.client.delete(self._key(key))
        except Exception as exc:  # noqa: BLE001
            raise RateLimitStoreError("Redis rate limit store unavailable") from exc

    def get_ttl(self, key: str) -> int:
        try:
            ttl = int(self.client.ttl(self._key(key)))
            return max(0, ttl)
        except Exception as exc:  # noqa: BLE001
            raise RateLimitStoreError("Redis rate limit store unavailable") from exc
