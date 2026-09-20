"""Database initialization / bootstrap.

Used by ``python -m app.db.init_db`` (see docker-compose and README). Creates
all tables from the ORM metadata. For production, prefer Alembic migrations,
which are also provided.
"""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.db.base import Base
from app.db.session import dispose_engine, get_engine

# Import models so metadata is fully populated before create_all.
import app.models  # noqa: F401

logger = get_logger("app.db.init_db")


async def init_models() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema ensured (%d tables).", len(Base.metadata.tables))


async def _main() -> None:
    await init_models()
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_main())