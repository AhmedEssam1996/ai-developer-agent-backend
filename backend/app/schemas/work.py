"""Schemas for normalized work data: emails, events, messages, tasks, timeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    subject: str
    body_preview: str
    sender_email: str
    sender_name: str
    to_recipients: list[str] = Field(default_factory=list)
    received_at: datetime | None = None
    is_read: bool
    has_attachments: bool
    priority: str
    needs_reply: bool
    is_important: bool
    project_id: uuid.UUID | None = None
    web_link: str | None = None


class CalendarEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    subject: str
    body_preview: str
    starts_at: datetime
    ends_at: datetime
    is_all_day: bool
    location: str
    organizer_email: str
    attendees: list[dict[str, Any]] = Field(default_factory=list)
    is_online_meeting: bool
    join_url: str | None = None
    response_status: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    conversation_id: str
    conversation_name: str
    sender_email: str
    sender_name: str
    body: str
    direction: str
    sent_at: datetime | None = None
    is_mention: bool


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    title: str
    description: str
    status: str
    priority: str
    due_at: datetime | None = None
    completed_at: datetime | None = None
    assignee_email: str | None = None
    assignee_name: str | None = None
    project_id: uuid.UUID | None = None
    progress: int
    is_overdue: bool
    web_link: str | None = None


class CommitmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    direction: str
    status: str
    text: str
    counterparty_email: str | None = None
    counterparty_name: str | None = None
    due_at: datetime | None = None
    confidence: float
    source: str
    source_ref: str | None = None
    project_id: uuid.UUID | None = None
    acknowledged: bool


class TimelineItem(BaseModel):
    """A unified, provider-agnostic timeline entry."""

    id: str
    source: str
    type: str
    timestamp: datetime | None
    title: str
    summary: str = ""
    people: list[str] = Field(default_factory=list)
    project: str | None = None
    priority: str = "normal"
    ref_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    items: list[TimelineItem]
    next_cursor: str | None = None


class Paginated(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int