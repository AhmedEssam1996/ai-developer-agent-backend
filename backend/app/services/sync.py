"""Incremental synchronization engine.

Pulls from integration adapters, normalizes, and upserts into PostgreSQL using
per-provider ``sync_states`` checkpoints. Re-syncs are idempotent (unique
constraints on source+external_id) and incremental (checkpoint timestamps),
so we never continuously re-fetch everything.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.events.bus import DomainEvent, event_bus
from app.models.enums import IntegrationStatus, SyncStatus
from app.models.operations import SyncState
from app.services import integration_service, normalization

logger = get_logger("app.services.sync")

RESOURCES = ("emails", "calendar", "teams", "tasks", "projects")
_DEFAULT_LOOKBACK = timedelta(days=14)


@dataclass
class SyncOutcome:
    provider: str
    resource: str
    fetched: int = 0
    upserted: int = 0
    errors: int = 0
    message: str = ""


async def _get_state(
    session: AsyncSession, *, organization_id: uuid.UUID, provider: str, resource: str
) -> SyncState:
    state = await session.scalar(
        select(SyncState).where(
            SyncState.organization_id == organization_id,
            SyncState.provider == provider,
            SyncState.resource == resource,
        )
    )
    if state is None:
        state = SyncState(organization_id=organization_id, provider=provider, resource=resource)
        session.add(state)
        await session.flush()
    return state


def _checkpoint_since(state: SyncState) -> datetime:
    if state.cursor and state.last_synced_at:
        try:
            value = json.loads(state.cursor).get("since")
            if value:
                return datetime.fromisoformat(value)
        except (json.JSONDecodeError, ValueError):
            pass
    return datetime.now(timezone.utc) - _DEFAULT_LOOKBACK


def _store_checkpoint(state: SyncState, since: datetime) -> None:
    state.cursor = json.dumps({"since": since.astimezone(timezone.utc).isoformat()})


async def sync_resource(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    provider: str,
    resource: str,
    full: bool = False,
) -> SyncOutcome:
    outcome = SyncOutcome(provider=provider, resource=resource)
    state = await _get_state(
        session, organization_id=organization_id, provider=provider, resource=resource
    )
    since = datetime.now(timezone.utc) - _DEFAULT_LOOKBACK if full else _checkpoint_since(state)
    started = datetime.now(timezone.utc)
    try:
        adapters = await integration_service.resolve_adapters(
            session, organization_id=organization_id
        )
        if resource == "emails":
            items = await adapters.mail.list_messages(since=since, top=50)
            for item in items:
                await normalization.upsert_email(
                    session, organization_id=organization_id, email=item
                )
            outcome.fetched = len(items)
        elif resource == "calendar":
            items = await adapters.calendar.list_events(
                start=datetime.now(timezone.utc),
                end=datetime.now(timezone.utc) + timedelta(days=14),
            )
            for item in items:
                await normalization.upsert_calendar_event(
                    session, organization_id=organization_id, event=item
                )
            outcome.fetched = len(items)
        elif resource == "teams":
            items = await adapters.teams.list_messages(since=since, top=40)
            for item in items:
                await normalization.upsert_message(
                    session, organization_id=organization_id, message=item
                )
            outcome.fetched = len(items)
        elif resource == "projects":
            projects = await adapters.tasks.list_projects()
            for project in projects:
                await normalization.upsert_project(
                    session, organization_id=organization_id, project=project
                )
            outcome.fetched = len(projects)
        elif resource == "tasks":
            tasks = await adapters.tasks.list_tasks(top=100)
            for task in tasks:
                project_id = None
                if task.project_external_id:
                    project_id = await _resolve_project_id(
                        session, organization_id, task.project_external_id
                    )
                await normalization.upsert_task(
                    session, organization_id=organization_id, task=task, project_id=project_id
                )
            outcome.fetched = len(tasks)
        outcome.upserted = outcome.fetched
        state.status = SyncStatus.SUCCEEDED.value
        state.last_synced_at = started
        state.last_error = None
        state.items_synced = (state.items_synced or 0) + outcome.upserted
        state.consecutive_failures = 0
        _store_checkpoint(state, started)
        await _touch_integration(session, organization_id, provider)
        await event_bus.publish(
            DomainEvent(
                kind="sync_completed",
                organization_id=str(organization_id),
                data={"provider": provider, "resource": resource, "count": outcome.upserted},
            )
        )
    except Exception as exc:  # map to safe state; never leak raw exception
        outcome.errors = 1
        outcome.message = str(exc)
        state.status = SyncStatus.FAILED.value
        state.last_error = str(exc)[:500]
        state.last_synced_at = started
        state.consecutive_failures = (state.consecutive_failures or 0) + 1
        logger.warning("Sync %s/%s failed: %s", provider, resource, exc)
        await event_bus.publish(
            DomainEvent(
                kind="sync_failed",
                organization_id=str(organization_id),
                data={"provider": provider, "resource": resource, "message": outcome.message},
            )
        )
    await session.flush()
    return outcome


async def _resolve_project_id(
    session: AsyncSession, organization_id: uuid.UUID, external_id: str
) -> uuid.UUID | None:
    from app.models.work import Project

    project = await session.scalar(
        select(Project).where(
            Project.organization_id == organization_id, Project.external_id == external_id
        )
    )
    return project.id if project else None


async def _touch_integration(
    session: AsyncSession, organization_id: uuid.UUID, provider: str
) -> None:
    integration = await integration_service.get_integration(
        session, organization_id=organization_id, provider=provider
    )
    if integration is None:
        return
    integration.last_synced_at = datetime.now(timezone.utc)
    if integration.status != IntegrationStatus.CONNECTED.value:
        integration.status = IntegrationStatus.CONNECTED.value


async def sync_all(
    session: AsyncSession, *, organization_id: uuid.UUID, full: bool = False
) -> list[SyncOutcome]:
    outcomes: list[SyncOutcome] = []
    for provider, resources in (
        ("outlook", ("emails", "calendar")),
        ("teams", ("teams",)),
        ("goodday", ("projects", "tasks")),
    ):
        for resource in resources:
            outcomes.append(
                await sync_resource(
                    session,
                    organization_id=organization_id,
                    provider=provider,
                    resource=resource,
                    full=full,
                )
            )
    return outcomes