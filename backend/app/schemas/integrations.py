"""Integration & sync schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    status: str
    scopes: str
    account_label: str | None = None
    last_synced_at: datetime | None = None
    last_error: str | None = None


class IntegrationOverview(BaseModel):
    """What the sidebar and settings pages render per provider."""

    provider: str
    display_name: str
    description: str
    connected: bool
    status: str
    configured: bool
    account_label: str | None = None
    last_synced_at: datetime | None = None
    last_error: str | None = None
    is_mock: bool = False
    connect_url: str | None = None


class ConnectUrlResponse(BaseModel):
    provider: str
    authorize_url: str


class SyncRequest(BaseModel):
    provider: str | None = None
    resource: str | None = None
    full: bool = False


class SyncStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    resource: str
    status: str
    last_synced_at: datetime | None = None
    last_error: str | None = None
    items_synced: int
    consecutive_failures: int


class SyncResult(BaseModel):
    provider: str
    resource: str
    fetched: int
    upserted: int
    errors: int = 0
    message: str = ""