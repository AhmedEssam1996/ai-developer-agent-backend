"""Agent context & memory assembly.

Builds the working context the model sees: a compact snapshot of the user's
world (today's counts, key tasks, upcoming meetings) plus durable project
facts. Structured facts and source records live in PostgreSQL; this module only
*assembles* them. We do not vectorize every row — semantic memory is opt-in via
``memory_items``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work import CalendarEvent, Email, Project, Task


@dataclass
class WorkingContext:
    summary: str
    facts: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)


async def build_working_context(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_email: str = "",
) -> WorkingContext:
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=2)

    upcoming = list(
        await session.scalars(
            select(CalendarEvent)
            .where(
                CalendarEvent.organization_id == organization_id,
                CalendarEvent.ends_at >= now,
                CalendarEvent.starts_at <= horizon,
            )
            .order_by(CalendarEvent.starts_at)
            .limit(6)
        )
    )
    overdue = list(
        await session.scalars(
            select(Task)
            .where(Task.organization_id == organization_id, Task.is_overdue.is_(True))
            .order_by(Task.due_at)
            .limit(6)
        )
    )
    unread = list(
        await session.scalars(
            select(Email)
            .where(
                Email.organization_id == organization_id,
                Email.is_important.is_(True),
            )
            .order_by(desc(Email.received_at))
            .limit(6)
        )
    )
    projects = list(
        await session.scalars(
            select(Project).where(Project.organization_id == organization_id).limit(10)
        )
    )

    facts: list[str] = []
    if upcoming:
        names = ", ".join(e.subject for e in upcoming)
        facts.append(f"Upcoming meetings: {names}.")
    if overdue:
        names = ", ".join(t.title for t in overdue)
        facts.append(f"Overdue tasks: {names}.")
    if unread:
        names = ", ".join(e.subject for e in unread)
        facts.append(f"Important recent emails: {names}.")

    summary = (
        f"{len(upcoming)} upcoming meetings, {len(overdue)} overdue tasks, "
        f"{len(unread)} important emails in the last period."
    )
    return WorkingContext(
        summary=summary, facts=facts, projects=[p.name for p in projects]
    )


async def record_memory(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    kind: str,
    key: str,
    content: str,
    data: dict[str, Any] | None = None,
    embedding: list[float] | None = None,
) -> None:
    """Persist a durable memory item (structured fact by default).

    The embedding column stores JSON text for portability; it is only set when
    an embedding is explicitly provided (semantic memory is opt-in).
    """
    import json

    from app.models.operations import MemoryItem

    item = MemoryItem(
        organization_id=organization_id,
        kind=kind,
        key=key,
        content=content,
        data=json.dumps(data or {}, default=str),
        embedding=json.dumps(embedding) if embedding is not None else None,
    )
    session.add(item)
    await session.flush()


async def search_memory(
    session: AsyncSession, *, organization_id: uuid.UUID, key_like: str, limit: int = 5
) -> list[dict[str, Any]]:
    from app.models.operations import MemoryItem

    rows = list(
        await session.scalars(
            select(MemoryItem)
            .where(
                MemoryItem.organization_id == organization_id,
                MemoryItem.key.ilike(f"%{key_like}%"),
            )
            .limit(limit)
        )
    )
    return [{"key": r.key, "content": r.content, "kind": r.kind} for r in rows]
