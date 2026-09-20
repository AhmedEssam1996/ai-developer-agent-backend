"""Integration connection + OAuth account models.

Tokens are stored **encrypted** (see ``app.security.crypto``). The ORM stores
ciphertext only; plaintext never touches the database.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import IntegrationStatus


class Integration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per (organization, provider) connection."""

    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_integration_org_provider"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=IntegrationStatus.DISCONNECTED.value, nullable=False
    )
    scopes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    account_label: Mapped[str | None] = mapped_column(String(320), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    oauth_account: Mapped["OAuthAccount | None"] = relationship(
        back_populates="integration", cascade="all, delete-orphan", uselist=False
    )


class OAuthAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Encrypted OAuth tokens for an integration."""

    __tablename__ = "oauth_accounts"

    integration_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String(32), default="Bearer", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scope: Mapped[str] = mapped_column(Text, default="", nullable=False)

    integration: Mapped[Integration] = relationship(back_populates="oauth_account")