"""Rate limiting.

A fixed-window counter backed by Redis when available, with an in-process
fallback so tests and single-worker dev environments keep working. The limiter
is keyed by an arbitrary string (e.g. ``user:<id>`` or ``ip:<addr>``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.security.rate_limit")


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_in: int


class _MemoryStore:
    """Very small in-process fixed-window store (dev/test fallback)."""

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[int, int]] = {}  # key -> (window_start, count)

    def incr(self, key: str, window: int) -> tuple[int, int]:
        now = int(time.time())
        window_start = now - (now % window)
        start, count = self._buckets.get(key, (window_start, 0))
        if start != window_start:
            start, count = window_start, 0
        count += 1
        self._buckets[key] = (start, count)
        reset_in = window - (now - window_start)
        return count, max(reset_in, 1)


class RateLimiter:
    def __init__(self, limit: int | None = None, window_seconds: int = 60) -> None:
        self.limit = limit or settings.rate_limit_per_minute
        self.window = window_seconds
        self._memory = _MemoryStore()
        self._redis = None

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
            await client.ping()
            self._redis = client
        except Exception:  # pragma: no cover - depends on environment
            logger.debug("Redis unavailable; using in-memory rate limiter.")
            self._redis = False
        return self._redis

    async def check(self, key: str, *, cost: int = 1) -> RateLimitResult:
        window = self.window
        redis = await self._get_redis()
        if redis:
            bucket = f"rl:{key}:{int(time.time()) // window}"
            try:
                count = await redis.incrby(bucket, cost)
                if count == cost:
                    await redis.expire(bucket, window)
                ttl = await redis.ttl(bucket)
                remaining = max(self.limit - count, 0)
                return RateLimitResult(count <= self.limit, remaining, max(ttl, 1))
            except Exception:  # pragma: no cover
                logger.debug("Redis rate-limit error; falling back to memory.")

        count, reset_in = self._memory.incr(key, window)
        remaining = max(self.limit - count, 0)
        return RateLimitResult(count <= self.limit, remaining, reset_in)


limiter = RateLimiter()