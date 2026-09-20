"""Audit logging service.

Append-only records of security-relevant events (auth, approvals, writes).
Never blocks the primary operation: failures are logged but swallowed.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.operations import AuditLog

logger = get_logger("app.services.audit")


async def record_audit(
    session: AsyncSession,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    outcome: str = "success",
    detail: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Write an audit entry (best-effort)."""
    try:
        entry = AuditLog(
            action=action,
            user_id=user_id,
            organization_id=organization_id,
            target_type=target_type,
            target_id=target_id,
            outcome=outcome,
            detail=json.dumps(detail or {}, default=str),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(entry)
        await session.flush()
    except Exception:  # pragma: no cover - audit must never break the request
        logger.exception("Failed to write audit log for action=%s", action)