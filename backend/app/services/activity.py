"""Activity feed service.

Records user-facing activity ("New important email detected", agent status)
and publishes it to the realtime event bus so the frontend updates without a
refresh. Kept separate from audit logs (which are security-focused).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.bus import DomainEvent, event_bus
from app.models.operations import ActivityEvent


async def record_activity(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    kind: str,
    title: str,
    detail: str = "",
    source: str | None = None,
    level: str = "info",
    run_id: uuid.UUID | None = None,
    ref_type: str | None = None,
    ref_id: str | None = None,
    data: dict[str, Any] | None = None,
    publish: bool = True,
) -> ActivityEvent:
    event = ActivityEvent(
        organization_id=organization_id,
        kind=kind,
        title=title,
        detail=detail,
        source=source,
        level=level,
        run_id=run_id,
        ref_type=ref_type,
        ref_id=ref_id,
        data=json.dumps(data or {}, default=str),
    )
    session.add(event)
    await session.flush()

    if publish:
        await event_bus.publish(
            DomainEvent(
                kind="activity",
                organization_id=str(organization_id),
                data={
                    "id": str(event.id),
                    "kind": kind,
                    "title": title,
                    "detail": detail,
                    "source": source,
                    "level": level,
                    "run_id": str(run_id) if run_id else None,
                },
            )
        )
    return event


async def list_activity(
    session: AsyncSession, *, organization_id: uuid.UUID, limit: int = 50
) -> list[ActivityEvent]:
    rows = await session.scalars(
        select(ActivityEvent)
        .where(ActivityEvent.organization_id == organization_id)
        .order_by(desc(ActivityEvent.created_at))
        .limit(limit)
    )
    return list(rows)