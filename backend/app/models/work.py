"""Normalized work data models.

These are provider-agnostic: every record from Outlook / Teams / GoodDay is
converted into one of these shapes by the integration layer. The UI and agent
never depend on a provider's raw schema.

Every externally-sourced record carries ``source`` + ``external_id`` with a
unique constraint so synchronization is idempotent.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, ExternalSourceMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MessageDirection, Priority, TaskStatus


class Person(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A human referenced across sources (sender, attendee, assignee)."""

    __tablename__ = "people"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_person_org_email"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="mywork", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A unit of work that groups tasks, emails, messages and events."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_project_org_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="mywork", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Email(UUIDPrimaryKeyMixin, TimestampMixin, ExternalSourceMixin, Base):
    """Normalized email message (Outlook)."""

    __tablename__ = "emails"
    __table_args__ = (
        UniqueConstraint("organization_id", "source", "external_id", name="uq_email_ext"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    body_preview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_email: Mapped[str] = mapped_column(String(320), default="", nullable=False, index=True)
    sender_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    to_recipients: Mapped[str] = mapped_column(Text, default="", nullable=False)  # JSON list
    cc_recipients: Mapped[str] = mapped_column(Text, default="", nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    importance: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    priority: Mapped[str] = mapped_column(
        String(16), default=Priority.NORMAL.value, nullable=False, index=True
    )
    needs_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    thread_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    web_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class CalendarEvent(UUIDPrimaryKeyMixin, TimestampMixin, ExternalSourceMixin, Base):
    """Normalized calendar event (Outlook Calendar)."""

    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "source", "external_id", name="uq_calendar_ext"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    body_preview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    location: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    organizer_email: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    attendees: Mapped[str] = mapped_column(Text, default="", nullable=False)  # JSON list
    is_online_meeting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    join_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_status: Mapped[str] = mapped_column(String(32), default="accepted", nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    web_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class Message(UUIDPrimaryKeyMixin, TimestampMixin, ExternalSourceMixin, Base):
    """Normalized chat message (Microsoft Teams)."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("organization_id", "source", "external_id", name="uq_message_ext"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    conversation_name: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), default="", nullable=False, index=True)
    sender_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    direction: Mapped[str] = mapped_column(
        String(16), default=MessageDirection.INBOUND.value, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    importance: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    is_mention: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    web_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class Task(UUIDPrimaryKeyMixin, TimestampMixin, ExternalSourceMixin, Base):
    """Normalized task (primarily GoodDay, extensible to others)."""

    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("organization_id", "source", "external_id", name="uq_task_ext"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=TaskStatus.OPEN.value, nullable=False, index=True
    )
    priority: Mapped[str] = mapped_column(
        String(16), default=Priority.NORMAL.value, nullable=False, index=True
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assignee_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    assignee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    project_external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_overdue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    web_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[str] = mapped_column(Text, default="{}", nullable=False)