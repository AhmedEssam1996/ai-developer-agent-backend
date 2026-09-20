"""Convert normalized integration DTOs into ORM rows idempotently.

Upserts key on ``(organization_id, source, external_id)`` so re-syncing the
same provider payload never duplicates rows. Classification of priority,
importance and overdue is centralized here so every source behaves consistently.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.integrations.base import (
    NormalizedCalendarEvent,
    NormalizedEmail,
    NormalizedMessage,
    NormalizedProject,
    NormalizedTask,
)
from app.models.enums import Priority, SourceType, TaskStatus
from app.models.work import (
    CalendarEvent,
    Email,
    Message,
    Project,
    Task,
)

_IMPORTANT_SENDER_HINTS = ("client", "escalation", "urgent", "proposal")


def _json(value: object) -> str:
    return json.dumps(value, default=str)


def classify_email_priority(email: NormalizedEmail) -> tuple[str, bool, bool]:
    """Return ``(priority, needs_reply, is_important)``."""
    importance = (email.importance or "normal").lower()
    text = f"{email.subject} {email.body_preview}".lower()
    needs_reply = any(
        kw in text for kw in ("please", "could you", "can you", "?", "request", "asap")
    )
    is_important = importance == "high" or any(h in text for h in _IMPORTANT_SENDER_HINTS)
    if importance == "high":
        priority = Priority.HIGH.value
    elif is_important:
        priority = Priority.HIGH.value
    else:
        priority = Priority.NORMAL.value
    if not email.is_read and priority == Priority.HIGH.value:
        priority = Priority.URGENT.value
    return priority, needs_reply, is_important


async def upsert_email(
    session: AsyncSession, *, organization_id: uuid.UUID, email: NormalizedEmail
) -> Email:
    existing = await session.scalar(
        select(Email).where(
            Email.organization_id == organization_id,
            Email.source == SourceType.OUTLOOK.value,
            Email.external_id == email.external_id,
        )
    )
    priority, needs_reply, is_important = classify_email_priority(email)
    if existing is None:
        existing = Email(
            organization_id=organization_id,
            source=SourceType.OUTLOOK.value,
            external_id=email.external_id,
            subject=email.subject,
        )
        session.add(existing)
    existing.subject = email.subject
    existing.body_preview = email.body_preview
    existing.body_html = email.body_html
    existing.sender_email = email.sender_email
    existing.sender_name = email.sender_name
    existing.to_recipients = _json(email.to_recipients)
    existing.cc_recipients = _json(email.cc_recipients)
    existing.received_at = email.received_at
    existing.is_read = email.is_read
    existing.has_attachments = email.has_attachments
    existing.importance = email.importance
    existing.priority = priority
    existing.needs_reply = needs_reply
    existing.is_important = is_important
    existing.thread_id = email.thread_id
    existing.web_link = email.web_link
    existing.raw = _json(email.raw)
    await session.flush()
    return existing


async def upsert_calendar_event(
    session: AsyncSession, *, organization_id: uuid.UUID, event: NormalizedCalendarEvent
) -> CalendarEvent:
    existing = await session.scalar(
        select(CalendarEvent).where(
            CalendarEvent.organization_id == organization_id,
            CalendarEvent.source == SourceType.OUTLOOK.value,
            CalendarEvent.external_id == event.external_id,
        )
    )
    now = datetime.now(timezone.utc)
    starts = event.starts_at or now
    ends = event.ends_at or starts
    if ends < starts:
        raise ValidationError("Calendar event end must be after start.")
    if existing is None:
        existing = CalendarEvent(
            organization_id=organization_id,
            source=SourceType.OUTLOOK.value,
            external_id=event.external_id,
            subject=event.subject,
            starts_at=starts,
            ends_at=ends,
        )
        session.add(existing)
    existing.subject = event.subject
    existing.body_preview = event.body_preview
    existing.starts_at = starts
    existing.ends_at = ends
    existing.is_all_day = event.is_all_day
    existing.location = event.location
    existing.organizer_email = event.organizer_email
    existing.attendees = _json(event.attendees)
    existing.is_online_meeting = event.is_online_meeting
    existing.join_url = event.join_url
    existing.response_status = event.response_status
    existing.web_link = event.web_link
    existing.raw = _json(event.raw)
    await session.flush()
    return existing


async def upsert_message(
    session: AsyncSession, *, organization_id: uuid.UUID, message: NormalizedMessage
) -> Message:
    existing = await session.scalar(
        select(Message).where(
            Message.organization_id == organization_id,
            Message.source == SourceType.TEAMS.value,
            Message.external_id == message.external_id,
        )
    )
    if existing is None:
        existing = Message(
            organization_id=organization_id,
            source=SourceType.TEAMS.value,
            external_id=message.external_id,
            conversation_id=message.conversation_id,
        )
        session.add(existing)
    existing.conversation_id = message.conversation_id
    existing.conversation_name = message.conversation_name
    existing.sender_email = message.sender_email
    existing.sender_name = message.sender_name
    existing.body = message.body
    existing.direction = message.direction
    existing.sent_at = message.sent_at
    existing.is_mention = message.is_mention
    existing.web_link = message.web_link
    existing.raw = _json(message.raw)
    await session.flush()
    return existing


async def upsert_project(
    session: AsyncSession, *, organization_id: uuid.UUID, project: NormalizedProject
) -> Project:
    existing = await session.scalar(
        select(Project).where(
            Project.organization_id == organization_id,
            Project.source == SourceType.GOODDAY.value,
            Project.external_id == project.external_id,
        )
    )
    if existing is None:
        # Name uniqueness is org+name; fall back to matching by name.
        existing = await session.scalar(
            select(Project).where(
                Project.organization_id == organization_id, Project.name == project.name
            )
        )
    if existing is None:
        existing = Project(
            organization_id=organization_id,
            source=SourceType.GOODDAY.value,
            external_id=project.external_id,
            name=project.name or "Untitled",
        )
        session.add(existing)
    existing.name = project.name or existing.name
    existing.description = project.description
    existing.external_id = project.external_id
    await session.flush()
    return existing


async def upsert_task(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    task: NormalizedTask,
    project_id: uuid.UUID | None = None,
) -> Task:
    existing = await session.scalar(
        select(Task).where(
            Task.organization_id == organization_id,
            Task.source == SourceType.GOODDAY.value,
            Task.external_id == task.external_id,
        )
    )
    now = datetime.now(timezone.utc)
    due = task.due_at
    is_overdue = bool(
        due and due < now and task.status not in (TaskStatus.DONE.value, TaskStatus.CANCELLED.value)
    )
    if existing is None:
        existing = Task(
            organization_id=organization_id,
            source=SourceType.GOODDAY.value,
            external_id=task.external_id,
            title=task.title or "Untitled task",
        )
        session.add(existing)
    existing.title = task.title or existing.title
    existing.description = task.description
    existing.status = task.status
    existing.priority = task.priority
    existing.due_at = due
    existing.completed_at = task.completed_at
    existing.assignee_email = task.assignee_email
    existing.assignee_name = task.assignee_name
    existing.project_external_id = task.project_external_id
    if project_id is not None:
        existing.project_id = project_id
    existing.progress = task.progress
    existing.is_overdue = is_overdue
    existing.web_link = task.web_link
    existing.raw = _json(task.raw)
    await session.flush()
    return existing