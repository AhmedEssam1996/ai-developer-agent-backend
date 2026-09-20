"""Dashboard ("Today") aggregation and the unified work timeline.

All values are derived from normalized PostgreSQL records — nothing here is
hardcoded. The dashboard answers "what needs my attention?" across every
connected source.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.registry import is_mock_mode
from app.models.enums import CommitmentStatus, EventType, SourceType, TaskStatus
from app.models.operations import Commitment
from app.models.work import CalendarEvent, Email, Message, Task
from app.schemas.dashboard import AttentionCounts, DashboardResponse
from app.schemas.work import (
    CalendarEventOut,
    CommitmentOut,
    EmailOut,
    TaskOut,
    TimelineItem,
)


def greeting_for(now: datetime, name: str) -> str:
    hour = now.hour
    if hour < 12:
        part = "GOOD MORNING"
    elif hour < 18:
        part = "GOOD AFTERNOON"
    else:
        part = "GOOD EVENING"
    return f"{part}, {name.upper()}" if name else part


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _email_out(email: Email) -> EmailOut:
    return EmailOut(
        id=email.id,
        source=email.source,
        external_id=email.external_id,
        subject=email.subject,
        body_preview=email.body_preview,
        sender_email=email.sender_email,
        sender_name=email.sender_name,
        to_recipients=_loads(email.to_recipients, []),
        received_at=email.received_at,
        is_read=email.is_read,
        has_attachments=email.has_attachments,
        priority=email.priority,
        needs_reply=email.needs_reply,
        is_important=email.is_important,
        project_id=email.project_id,
        web_link=email.web_link,
    )


async def build_dashboard(
    session: AsyncSession, *, organization_id: uuid.UUID, user_name: str = ""
) -> DashboardResponse:
    now = datetime.now(timezone.utc)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    week_ahead = now + timedelta(days=7)

    important_emails = list(
        await session.scalars(
            select(Email)
            .where(Email.organization_id == organization_id, Email.is_important.is_(True))
            .order_by(desc(Email.received_at))
            .limit(6)
        )
    )
    overdue_tasks = list(
        await session.scalars(
            select(Task)
            .where(Task.organization_id == organization_id, Task.is_overdue.is_(True))
            .order_by(Task.due_at)
            .limit(6)
        )
    )
    today_tasks = list(
        await session.scalars(
            select(Task)
            .where(
                Task.organization_id == organization_id,
                Task.due_at >= now,
                Task.due_at <= end_of_day,
                Task.status.notin_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value]),
            )
            .order_by(Task.due_at)
            .limit(8)
        )
    )
    upcoming_events = list(
        await session.scalars(
            select(CalendarEvent)
            .where(
                CalendarEvent.organization_id == organization_id,
                CalendarEvent.ends_at >= now,
                CalendarEvent.starts_at <= week_ahead,
            )
            .order_by(CalendarEvent.starts_at)
            .limit(8)
        )
    )
    you_owe = list(
        await session.scalars(
            select(Commitment)
            .where(
                Commitment.organization_id == organization_id,
                Commitment.direction == "i_owe",
                Commitment.status.in_(
                    [CommitmentStatus.OPEN.value, CommitmentStatus.OVERDUE.value]
                ),
            )
            .order_by(Commitment.due_at)
            .limit(6)
        )
    )
    waiting_for = list(
        await session.scalars(
            select(Commitment)
            .where(
                Commitment.organization_id == organization_id,
                Commitment.direction == "owed_to_me",
                Commitment.status.in_(
                    [CommitmentStatus.OPEN.value, CommitmentStatus.OVERDUE.value]
                ),
            )
            .order_by(Commitment.due_at)
            .limit(6)
        )
    )

    urgent: list[TimelineItem] = []
    for task in overdue_tasks[:3]:
        urgent.append(
            TimelineItem(
                id=f"task:{task.id}",
                source=SourceType.GOODDAY.value,
                type=EventType.TASK.value,
                timestamp=task.due_at,
                title=task.title,
                summary="Overdue task",
                priority="urgent",
                ref_id=task.id,
            )
        )
    for email in important_emails[:3]:
        urgent.append(
            TimelineItem(
                id=f"email:{email.id}",
                source=SourceType.OUTLOOK.value,
                type=EventType.EMAIL.value,
                timestamp=email.received_at,
                title=email.subject,
                summary=email.sender_name or email.sender_email,
                people=[email.sender_name or email.sender_email],
                priority=email.priority,
                ref_id=email.id,
            )
        )
    imminent = [e for e in upcoming_events if e.starts_at <= now + timedelta(hours=6)]
    for event in imminent[:2]:
        urgent.append(
            TimelineItem(
                id=f"event:{event.id}",
                source=SourceType.OUTLOOK.value,
                type=EventType.CALENDAR_EVENT.value,
                timestamp=event.starts_at,
                title=event.subject,
                summary="Starting soon",
                priority="high",
                ref_id=event.id,
            )
        )
    urgent.sort(key=lambda i: i.timestamp or now)

    counts = AttentionCounts(
        requiring_action=len(you_owe) + len(today_tasks),
        overdue_tasks=len(overdue_tasks),
        important_emails=len(important_emails),
        upcoming_meetings=len([e for e in upcoming_events if e.starts_at.date() == now.date()]),
    )

    warning: list[str] = []
    if is_mock_mode():
        warning.append("Development data mode is enabled — records are synthetic.")

    return DashboardResponse(
        greeting=greeting_for(now, user_name),
        generated_at=now,
        counts=counts,
        urgent=urgent,
        upcoming_events=[CalendarEventOut.model_validate(e) for e in upcoming_events],
        waiting_for=[CommitmentOut.model_validate(c) for c in waiting_for],
        you_owe=[CommitmentOut.model_validate(c) for c in you_owe],
        important_emails=[_email_out(e) for e in important_emails],
        overdue_tasks=[TaskOut.model_validate(t) for t in overdue_tasks],
        today_tasks=[TaskOut.model_validate(t) for t in today_tasks],
        integrations_warning=warning,
        is_development_data=is_mock_mode(),
        meta={"timezone": "UTC"},
    )


async def build_timeline(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    limit: int = 50,
    sources: list[str] | None = None,
    since: datetime | None = None,
) -> list[TimelineItem]:
    """Merge emails, events, messages and tasks into one normalized timeline."""
    items: list[TimelineItem] = []

    email_stmt = select(Email).where(Email.organization_id == organization_id)
    event_stmt = select(CalendarEvent).where(CalendarEvent.organization_id == organization_id)
    message_stmt = select(Message).where(Message.organization_id == organization_id)
    task_stmt = select(Task).where(Task.organization_id == organization_id)

    if since:
        email_stmt = email_stmt.where(Email.received_at >= since)
        event_stmt = event_stmt.where(CalendarEvent.starts_at >= since)
        message_stmt = message_stmt.where(Message.sent_at >= since)
        task_stmt = task_stmt.where(Task.due_at >= since)

    want = set(sources) if sources else {"outlook", "teams", "goodday"}
    per_source = max(limit, 10)

    if "outlook" in want:
        for e in await session.scalars(
            email_stmt.order_by(desc(Email.received_at)).limit(per_source)
        ):
            items.append(
                TimelineItem(
                    id=f"email:{e.id}",
                    source=e.source,
                    type=EventType.EMAIL.value,
                    timestamp=e.received_at,
                    title=e.subject,
                    summary=e.body_preview[:200],
                    people=[e.sender_name or e.sender_email],
                    priority=e.priority,
                    ref_id=e.id,
                    metadata={"needs_reply": e.needs_reply, "is_important": e.is_important},
                )
            )
        for ev in await session.scalars(
            event_stmt.order_by(CalendarEvent.starts_at).limit(per_source)
        ):
            items.append(
                TimelineItem(
                    id=f"event:{ev.id}",
                    source=ev.source,
                    type=EventType.CALENDAR_EVENT.value,
                    timestamp=ev.starts_at,
                    title=ev.subject,
                    summary=ev.body_preview[:200],
                    people=[a.get("email", "") for a in _loads(ev.attendees, [])],
                    priority="normal",
                    ref_id=ev.id,
                    metadata={"join_url": ev.join_url, "location": ev.location},
                )
            )
    if "teams" in want:
        for m in await session.scalars(
            message_stmt.order_by(desc(Message.sent_at)).limit(per_source)
        ):
            items.append(
                TimelineItem(
                    id=f"message:{m.id}",
                    source=m.source,
                    type=EventType.TEAMS_MESSAGE.value,
                    timestamp=m.sent_at,
                    title=m.conversation_name or "Teams conversation",
                    summary=m.body[:200],
                    people=[m.sender_name or m.sender_email],
                    priority="high" if m.is_mention else "normal",
                    ref_id=m.id,
                    metadata={"conversation_id": m.conversation_id, "is_mention": m.is_mention},
                )
            )
    if "goodday" in want:
        for t in await session.scalars(
            task_stmt.order_by(desc(Task.is_overdue), Task.due_at).limit(per_source)
        ):
            items.append(
                TimelineItem(
                    id=f"task:{t.id}",
                    source=t.source,
                    type=EventType.TASK.value,
                    timestamp=t.due_at,
                    title=t.title,
                    summary=t.description[:200] or t.status,
                    people=[t.assignee_name or (t.assignee_email or "")],
                    priority=t.priority,
                    ref_id=t.id,
                    metadata={"status": t.status, "is_overdue": t.is_overdue},
                )
            )

    items.sort(
        key=lambda i: i.timestamp or datetime.min.replace(tzinfo=timezone.utc), reverse=True
    )
    return items[:limit]