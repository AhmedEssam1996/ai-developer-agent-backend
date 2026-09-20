"""Aggregate all API routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import agent, auth, integrations, work

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(integrations.router)
api_router.include_router(work.router)
api_router.include_router(agent.router)

__all__ = ["api_router"]