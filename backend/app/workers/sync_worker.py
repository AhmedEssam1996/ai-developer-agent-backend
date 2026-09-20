"""Background sync worker.

Periodically pulls each organization's connected sources through the sync
engine, refreshes commitments, and emits realtime activity. Uses checkpoints so
re-fetching is incremental; failures mark the integration's sync_state without
stopping other work.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.enums import IntegrationStatus
from app.models.integrations import Integration
from app.services import activity, commitments, sync

logger = get_logger("app.workers.sync_worker")

# Give the app a moment to finish starting before the first pass.
_INITIAL_DELAY_SECONDS = 5


async def run_sync_pass() -> int:
    """Run one sync cycle across all organizations. Returns orgs processed."""
    processed = 0
    async with session_scope() as session:
        rows = await session.scalars(
            select(Integration)
            .where(Integration.status == IntegrationStatus.CONNECTED.value)
            .distinct(Integration.organization_id)
        )
        organization_ids = [row.organization_id for row in rows]

        for organization_id in organization_ids:
            processed += 1
            try:
                outcomes = await sync.sync_all(session, organization_id=organization_id)
                synced = sum(o.upserted for o in outcomes)
                failed = [o for o in outcomes if o.errors]

                await commitments.scan_emails(session, organization_id=organization_id)
                await commitments.scan_messages(session, organization_id=organization_id)
                await commitments.refresh_overdue(session, organization_id=organization_id)

                if synced:
                    await activity.record_activity(
                        session,
                        organization_id=organization_id,
                        kind="sync_completed",
                        title=f"Synced {synced} item{'s' if synced != 1 else ''}",
                        detail="Background synchronization completed.",
                        level="info",
                    )
                for outcome in failed:
                    await activity.record_activity(
                        session,
                        organization_id=organization_id,
                        kind="sync_failed",
                        title=f"{outcome.provider} sync failed",
                        detail=outcome.message[:300],
                        source=outcome.provider,
                        level="warning",
                    )
            except Exception as exc:  # keep the loop alive for other orgs
                logger.warning("Sync pass failed for org %s: %s", organization_id, exc)
    return processed


async def sync_loop() -> None:
    """Continuously run sync passes until cancelled."""
    await asyncio.sleep(_INITIAL_DELAY_SECONDS)
    interval = max(settings.sync_interval_seconds, 30)
    while True:
        try:
            count = await run_sync_pass()
            logger.info("Sync pass completed for %d organization(s).", count)
        except asyncio.CancelledError:  # graceful shutdown
            raise
        except Exception:  # never let the worker die
            logger.exception("Unexpected error in sync loop")
        await asyncio.sleep(interval)