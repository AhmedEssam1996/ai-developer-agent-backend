"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine

logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Starting %s (env=%s, integration_mode=%s)",
                settings.app_name, settings.environment, settings.integration_mode)

    worker_task = None
    if settings.sync_enabled:
        from app.workers.sync_worker import sync_loop

        worker_task = asyncio.create_task(sync_loop())

    yield

    if worker_task is not None:
        worker_task.cancel()
    await dispose_engine()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI Work Operating System — unified work context and agent.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """Map domain errors to structured, user-safe responses."""
    return JSONResponse(status_code=exc.http_status, content=exc.to_payload())


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    """Never leak raw exceptions to clients."""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": "Something went wrong.", "details": {}},
    )


@app.get("/api/health", tags=["system"])
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "integration_mode": settings.integration_mode,
        "ai_configured": settings.openrouter_configured,
        "microsoft_configured": settings.microsoft_configured,
        "goodday_configured": settings.goodday_configured,
    }


app.include_router(api_router)