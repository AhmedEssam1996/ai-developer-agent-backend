"""Shared pytest fixtures.

Uses an in-memory SQLite database (via aiosqlite) so tests run without Postgres.
A tiny UUID/GUID shim maps ``postgresql.UUID`` columns onto SQLite's CHAR type.
"""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("INTEGRATION_MODE", "mock")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only-0000000000")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# Map Postgres UUID columns to a portable SQLite type before models import.
from sqlalchemy.dialects.postgresql import UUID as _PGUUID  # noqa: E402
from sqlalchemy import CHAR, TypeDecorator  # noqa: E402


class _PortableUUID(TypeDecorator):  # pragma: no cover - test shim
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return uuid.UUID(str(value))
        except ValueError:
            return value


import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session() -> AsyncSession:
    """Provide a fresh in-memory schema + session per test."""
    import app.models  # noqa: F401  (register metadata)
    from app.db.base import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as s:
        yield s
    await engine.dispose()