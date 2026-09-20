"""Integration lifecycle endpoints: status, connect, callback, disconnect, sync."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_session, rate_limited
from app.auth.dependencies import get_auth_context
from app.core.config import settings
from app.core.errors import ValidationError
from app.integrations.microsoft import MicrosoftOAuth
from app.integrations.registry import (
    SUPPORTED_PROVIDERS,
    description,
    display_name,
    is_mock_mode,
    provider_configured,
)
from app.models.enums import IntegrationStatus
from app.models.integrations import Integration
from app.models.operations import SyncState
from app.schemas.integrations import (
    ConnectUrlResponse,
    IntegrationOverview,
    SyncResult,
    SyncStateOut,
)
from app.services import audit, integration_service, sync

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# In-memory OAuth state store (single-process). Use Redis for multi-worker.
_OAUTH_STATES: dict[str, dict[str, str]] = {}


@router.get("", response_model=list[IntegrationOverview])
async def list_overview(
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[IntegrationOverview]:
    rows = await integration_service.list_integrations(
        session, organization_id=ctx.organization_id
    )
    by_provider = {r.provider: r for r in rows}

    overviews: list[IntegrationOverview] = []
    for provider in SUPPORTED_PROVIDERS:
        row = by_provider.get(provider)
        connected = bool(row and row.status == IntegrationStatus.CONNECTED.value)
        status_value = row.status if row else IntegrationStatus.DISCONNECTED.value
        connect_url = None
        if provider in ("outlook", "teams"):
            connect_url = f"/api/integrations/{provider}/connect"
        overviews.append(
            IntegrationOverview(
                provider=provider,
                display_name=display_name(provider),
                description=description(provider),
                connected=connected,
                status=status_value,
                configured=provider_configured(provider),
                account_label=row.account_label if row else None,
                last_synced_at=row.last_synced_at if row else None,
                last_error=row.last_error if row else None,
                is_mock=is_mock_mode(),
                connect_url=connect_url,
            )
        )
    return overviews


@router.get("/sync-states", response_model=list[SyncStateOut])
async def list_sync_states(
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[SyncStateOut]:
    rows = await session.scalars(
        select(SyncState).where(SyncState.organization_id == ctx.organization_id)
    )
    return [SyncStateOut.model_validate(r) for r in rows]


@router.get("/{provider}/connect", response_model=ConnectUrlResponse)
async def connect(
    provider: str,
    ctx: AuthContext = Depends(rate_limited),
    session: AsyncSession = Depends(get_session),
) -> ConnectUrlResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValidationError(f"Unsupported provider: {provider}")

    if is_mock_mode():
        # In mock mode we create a connection row that is clearly mock.
        integration = await integration_service.upsert_integration(
            session,
            organization_id=ctx.organization_id,
            provider=provider,
            status=IntegrationStatus.CONNECTED.value,
            scopes="mock",
            account_label="Development data",
        )
        integration.settings = json.dumps({"mock": True})
        await session.commit()
        return ConnectUrlResponse(provider=provider, authorize_url="mock://connected")

    if provider in ("outlook", "teams"):
        oauth = MicrosoftOAuth()
        state = oauth.generate_state()
        _OAUTH_STATES[state] = {
            "organization_id": str(ctx.organization_id),
            "user_id": str(ctx.user_id),
            "provider": provider,
        }
        url = oauth.build_authorize_url(state=state)
        return ConnectUrlResponse(provider=provider, authorize_url=url)

    if provider == "goodday":
        if not settings.goodday_configured:
            raise ValidationError(
                "GoodDay is not configured. Set GOODDAY_API_KEY or use INTEGRATION_MODE=mock."
            )
        integration = await integration_service.upsert_integration(
            session,
            organization_id=ctx.organization_id,
            provider="goodday",
            status=IntegrationStatus.CONNECTED.value,
            account_label="GoodDay",
        )
        integration.settings = json.dumps({"api_key": settings.goodday_api_key})
        await session.commit()
        return ConnectUrlResponse(provider="goodday", authorize_url="goodday://connected")

    raise ValidationError(f"Unsupported provider: {provider}")


@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """OAuth redirect target. Exchanges the code and stores encrypted tokens."""
    stored = _OAUTH_STATES.pop(state, None)
    if stored is None:
        return RedirectResponse(f"{settings.frontend_base_url}/integrations?error=state")

    oauth = MicrosoftOAuth()
    try:
        bundle = await oauth.exchange_code(code)
    except Exception:
        # Never leak raw provider errors to the browser.
        return RedirectResponse(f"{settings.frontend_base_url}/integrations?error=oauth")

    from app.models.identity import User

    org_id = stored["organization_id"]
    user_id = stored["user_id"]
    provider = stored["provider"]

    # Outlook connection implies the Microsoft Graph account is available for Teams too.
    for target in {provider, "outlook", "teams"}:
        integration = await integration_service.upsert_integration(
            session,
            organization_id=uuid.UUID(org_id),
            provider=target,
            status=IntegrationStatus.CONNECTED.value,
            scopes=bundle.scope,
        )
        await integration_service.store_tokens(session, integration=integration, bundle=bundle)

    user = await session.get(User, uuid.UUID(user_id))
    await audit.record_audit(
        session,
        action="integration.connect",
        user_id=user.id if user else None,
        organization_id=uuid.UUID(org_id),
        target_type="integration",
        target_id=provider,
    )
    await session.commit()
    return RedirectResponse(f"{settings.frontend_base_url}/integrations?connected={provider}")


@router.post("/{provider}/disconnect")
async def disconnect(
    provider: str,
    ctx: AuthContext = Depends(rate_limited),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValidationError("Unsupported provider.")
    if not is_mock_mode() and provider in ("outlook", "teams"):
        # Disconnecting the shared Microsoft app clears both.
        for target in ("outlook", "teams"):
            existing = await integration_service.get_integration(
                session, organization_id=ctx.organization_id, provider=target
            )
            if existing is not None:
                await integration_service.disconnect(
                    session, organization_id=ctx.organization_id, provider=target
                )
    else:
        existing = await integration_service.get_integration(
            session, organization_id=ctx.organization_id, provider=provider
        )
        if existing is not None:
            await integration_service.disconnect(
                session, organization_id=ctx.organization_id, provider=provider
            )
    await audit.record_audit(
        session,
        action="integration.disconnect",
        user_id=ctx.user_id,
        organization_id=ctx.organization_id,
        target_type="integration",
        target_id=provider,
    )
    await session.commit()
    return {"provider": provider, "status": IntegrationStatus.DISCONNECTED.value}


@router.post("/sync", response_model=list[SyncResult])
async def trigger_sync(
    full: bool = Query(default=False),
    ctx: AuthContext = Depends(rate_limited),
    session: AsyncSession = Depends(get_session),
) -> list[SyncResult]:
    outcomes = await sync.sync_all(
        session, organization_id=ctx.organization_id, full=full
    )
    await session.commit()
    return [
        SyncResult(
            provider=o.provider,
            resource=o.resource,
            fetched=o.fetched,
            upserted=o.upserted,
            errors=o.errors,
            message=o.message,
        )
        for o in outcomes
    ]


__all__ = ["router"]