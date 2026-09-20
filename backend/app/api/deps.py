"""Shared API dependencies (auth context, rate limiting, pagination)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthContext, get_auth_context
from app.core.errors import RateLimitedError
from app.db.session import get_session
from app.security.rate_limit import limiter


async def current_context(
    ctx: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    return ctx


async def rate_limited(
    request: Request, ctx: AuthContext = Depends(get_auth_context)
) -> AuthContext:
    """Per-user + per-path rate limit for mutating/expensive endpoints."""
    key = f"{ctx.user_id}:{request.url.path}"
    result = await limiter.check(key)
    if not result.allowed:
        raise RateLimitedError()
    return ctx


@dataclass
class Page:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination(page: int = 1, page_size: int = 25) -> Page:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    return Page(page=page, page_size=page_size)


__all__ = [
    "AuthContext",
    "Page",
    "current_context",
    "get_session",
    "pagination",
    "rate_limited",
]