"""Tests for sync engine, event bus, and logging improvements."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.events.bus import DomainEvent, EventBus
from app.integrations.base import (
    NormalizedEmail,
)
from app.services import sync as sync_service


# --- Event bus -------------------------------------------------------------


@pytest.mark.anyio
async def test_event_bus_publish_and_subscribe() -> None:
    bus = EventBus()
    queue = await bus.subscribe("org-1")
    await bus.publish(DomainEvent(kind="test", organization_id="org-1", data={"a": 1}))
    event = await asyncio.wait_for(queue.get(), timeout=1)
    assert event.kind == "test"
    assert event.data == {"a": 1}


@pytest.mark.anyio
async def test_event_bus_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    queue = await bus.subscribe("org-2")
    await bus.unsubscribe("org-2", queue)
    await bus.publish(DomainEvent(kind="late", organization_id="org-2"))
    assert queue.empty()


@pytest.mark.anyio
async def test_event_bus_drops_oldest_when_full() -> None:
    bus = EventBus()
    queue = await bus.subscribe("org-3")
    for i in range(205):
        await bus.publish(DomainEvent(kind="fill", organization_id="org-3", data={"i": i}))
    assert queue.qsize() <= 200


# --- Sync engine ------------------------------------------------------------


class _MockAdapters:
    def __init__(self) -> None:
        self.mail = MagicMock()
        self.calendar = MagicMock()
        self.teams = MagicMock()
        self.tasks = MagicMock()
        self.directory = MagicMock()


@pytest.mark.anyio
async def test_sync_resource_emails_upserts(session) -> None:
    org_id = uuid.uuid4()
    adapters = _MockAdapters()
    adapters.mail.list_messages = AsyncMock(
        return_value=[
            NormalizedEmail(
                external_id="e1",
                subject="Hello",
                body_preview="world",
                sender_email="a@b.com",
                received_at=datetime.now(timezone.utc),
            )
        ]
    )

    with patch(
        "app.services.integration_service.resolve_adapters", AsyncMock(return_value=adapters)
    ):
        outcome = await sync_service.sync_resource(
            session, organization_id=org_id, provider="outlook", resource="emails"
        )
    assert outcome.fetched == 1
    assert outcome.errors == 0
    from app.models.work import Email

    emails = list(await session.scalars(select(Email)))
    assert len(emails) == 1


@pytest.mark.anyio
async def test_sync_resource_records_failure_state(session) -> None:
    org_id = uuid.uuid4()
    adapters = _MockAdapters()
    adapters.mail.list_messages = AsyncMock(side_effect=RuntimeError("network down"))

    with patch(
        "app.services.integration_service.resolve_adapters", AsyncMock(return_value=adapters)
    ):
        outcome = await sync_service.sync_resource(
            session, organization_id=org_id, provider="outlook", resource="emails"
        )
    assert outcome.errors == 1
    assert "network down" in outcome.message


@pytest.mark.anyio
async def test_sync_all_runs_all_providers(session) -> None:
    org_id = uuid.uuid4()
    adapters = _MockAdapters()
    adapters.mail.list_messages = AsyncMock(return_value=[])
    adapters.calendar.list_events = AsyncMock(return_value=[])
    adapters.teams.list_messages = AsyncMock(return_value=[])
    adapters.tasks.list_projects = AsyncMock(return_value=[])
    adapters.tasks.list_tasks = AsyncMock(return_value=[])

    with patch(
        "app.services.integration_service.resolve_adapters", AsyncMock(return_value=adapters)
    ):
        outcomes = await sync_service.sync_all(session, organization_id=org_id)
    assert len(outcomes) == 5  # emails, calendar, teams, projects, tasks


# --- Sync worker -----------------------------------------------------------


@pytest.mark.anyio
async def test_sync_worker_handles_empty_orgs() -> None:
    from app.workers import sync_worker

    mock_session = AsyncMock()
    mock_session.scalars = AsyncMock(return_value=MagicMock())
    mock_session.scalars.return_value = MagicMock()
    mock_session.scalars.return_value.__aiter__ = AsyncMock(return_value=iter([]))

    with patch("app.workers.sync_worker.session_scope") as mock_scope:
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        with patch.object(sync_worker.sync, "sync_all", AsyncMock(return_value=[])):
            with patch.object(sync_worker.commitments, "scan_emails", AsyncMock()):
                with patch.object(sync_worker.commitments, "scan_messages", AsyncMock()):
                    with patch.object(sync_worker.commitments, "refresh_overdue", AsyncMock()):
                        with patch.object(sync_worker.activity, "record_activity", AsyncMock()):
                            count = await sync_worker.run_sync_pass()
                            assert count == 0