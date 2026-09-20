"""Dashboard / Today aggregation schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.work import (
    CalendarEventOut,
    CommitmentOut,
    EmailOut,
    TaskOut,
    TimelineItem,
)


class AttentionCounts(BaseModel):
    requiring_action: int = 0
    overdue_tasks: int = 0
    important_emails: int = 0
    upcoming_meetings: int = 0


class DashboardResponse(BaseModel):
    greeting: str
    generated_at: datetime
    counts: AttentionCounts
    urgent: list[TimelineItem] = Field(default_factory=list)
    upcoming_events: list[CalendarEventOut] = Field(default_factory=list)
    waiting_for: list[CommitmentOut] = Field(default_factory=list)
    you_owe: list[CommitmentOut] = Field(default_factory=list)
    important_emails: list[EmailOut] = Field(default_factory=list)
    overdue_tasks: list[TaskOut] = Field(default_factory=list)
    today_tasks: list[TaskOut] = Field(default_factory=list)
    integrations_warning: list[str] = Field(default_factory=list)
    is_development_data: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)