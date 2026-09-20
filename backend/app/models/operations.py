"""Operational models: commitments, sync state, audit log, memory, activity."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    CommitmentDirection,
    CommitmentStatus,
    MemoryKind,
    SyncStatus,
)


class Commitment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A promise detected in email/message traffic (I-owe / owed-to-me)."""

    __tablename__ = "commitments"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(
        String(16), default=CommitmentDirection.I_OWE.value, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=CommitmentStatus.OPEN.value, nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    owner_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_external_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    detected_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class SyncState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per (integration, resource) incremental sync checkpoint."""

    __tablename__ = "sync_states"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "provider", "resource", name="uq_sync_state_scope"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=SyncStatus.IDLE.value, nullable=False
    )
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)       # delta token / watermark
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_synced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only audit trail of security-relevant events."""

    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)


class MemoryItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Agent memory: durable facts, relationships, preferences, or embeddings.

    Not every row is vectorized. ``kind`` distinguishes structured memory
    (queries) from semantic memory (optional embedding).
    """

    __tablename__ = "memory_items"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(
        String(32), default=MemoryKind.FACT.value, nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(64), default="global", nullable=False, index=True)
    key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON structured
    subject_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    # embedding: stored as JSON list for portability; swap to pgvector when enabled.
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActivityEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User-facing realtime activity feed (and agent status) records."""

    __tablename__ = "activity_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    ref_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    data: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON