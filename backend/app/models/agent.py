"""Agent runtime models: runs, messages, actions, approvals."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ActionKind,
    ActionStatus,
    AgentRole,
    AgentRunStatus,
    ToolRisk,
)


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single agent invocation from a user."""

    __tablename__ = "agent_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), default=AgentRunStatus.PENDING.value, nullable=False, index=True
    )
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)

    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_call_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    actions: Mapped[list["AgentAction"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AgentMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single turn in the agent conversation (incl. tool observations)."""

    __tablename__ = "agent_messages"

    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), default=AgentRole.ASSISTANT.value, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    run: Mapped[AgentRun] = relationship(back_populates="messages")


class AgentAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tool call the agent proposed or executed."""

    __tablename__ = "agent_actions"

    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), default=ActionKind.READ.value, nullable=False)
    risk: Mapped[str] = mapped_column(String(16), default=ToolRisk.READ.value, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=ActionStatus.PROPOSED.value, nullable=False, index=True
    )
    arguments: Mapped[str] = mapped_column(Text, default="{}", nullable=False)   # JSON
    result: Mapped[str | None] = mapped_column(Text, nullable=True)               # JSON
    preview: Mapped[str | None] = mapped_column(Text, nullable=True)              # human summary
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    run: Mapped[AgentRun] = relationship(back_populates="actions")
    approval: Mapped["ActionApproval | None"] = relationship(
        back_populates="action", cascade="all, delete-orphan", uselist=False
    )


class ActionApproval(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Human approval record for a write action."""

    __tablename__ = "action_approvals"

    action_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_actions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    edited_arguments: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    action: Mapped[AgentAction] = relationship(back_populates="approval")