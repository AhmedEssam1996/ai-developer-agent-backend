"""Integration lifecycle: connect, disconnect, tokens, adapter resolution.

Owns the relationship between an organization's ``Integration`` rows, encrypted
OAuth tokens, and the adapters produced by the registry. Nothing else should
read tokens from the database directly.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import IntegrationAuthExpiredError, NotFoundError
from app.core.logging import get_logger
from app.integrations.base import TokenBundle
from app.integrations.microsoft import MicrosoftOAuth
from app.integrations.registry import ResolvedAdapters, build_adapters, is_mock_mode
from app.models.enums import IntegrationStatus
from app.models.integrations import Integration, OAuthAccount
from app.security.crypto import decrypt, encrypt

logger = get_logger("app.services.integration")


async def get_integration(
    session: AsyncSession, *, organization_id: uuid.UUID, provider: str
) -> Integration | None:
    return await session.scalar(
        select(Integration).where(
            Integration.organization_id == organization_id, Integration.provider == provider
        )
    )


async def list_integrations(
    session: AsyncSession, *, organization_id: uuid.UUID
) -> list[Integration]:
    result = await session.scalars(
        select(Integration).where(Integration.organization_id == organization_id)
    )
    return list(result)


async def upsert_integration(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    provider: str,
    status: str,
    scopes: str = "",
    account_label: str | None = None,
) -> Integration:
    integration = await get_integration(
        session, organization_id=organization_id, provider=provider
    )
    if integration is None:
        integration = Integration(
            organization_id=organization_id, provider=provider, status=status
        )
        session.add(integration)
    integration.status = status
    if scopes:
        integration.scopes = scopes
    if account_label:
        integration.account_label = account_label
    integration.last_error = None
    await session.flush()
    return integration


async def store_tokens(
    session: AsyncSession, *, integration: Integration, bundle: TokenBundle
) -> OAuthAccount:
    account = await session.scalar(
        select(OAuthAccount).where(OAuthAccount.integration_id == integration.id)
    )
    if account is None:
        account = OAuthAccount(integration_id=integration.id)
        session.add(account)
    account.access_token_enc = encrypt(bundle.access_token)
    if bundle.refresh_token:
        account.refresh_token_enc = encrypt(bundle.refresh_token)
    account.token_type = bundle.token_type
    account.expires_at = bundle.expires_at
    account.scope = bundle.scope
    await session.flush()
    return account


async def disconnect(
    session: AsyncSession, *, organization_id: uuid.UUID, provider: str
) -> None:
    integration = await get_integration(
        session, organization_id=organization_id, provider=provider
    )
    if integration is None:
        raise NotFoundError(f"{provider} is not connected.")
    account = await session.scalar(
        select(OAuthAccount).where(OAuthAccount.integration_id == integration.id)
    )
    if account is not None:
        await session.delete(account)
    integration.status = IntegrationStatus.DISCONNECTED.value
    integration.last_error = None
    await session.flush()


async def _valid_access_token(
    session: AsyncSession, *, organization_id: uuid.UUID
) -> str | None:
    """Return a valid Microsoft access token, refreshing when needed."""
    integration = await get_integration(
        session, organization_id=organization_id, provider="outlook"
    )
    if integration is None:
        # Teams shares the Microsoft app; fall back to a teams row if present.
        integration = await get_integration(
            session, organization_id=organization_id, provider="teams"
        )
    if integration is None:
        return None
    account = await session.scalar(
        select(OAuthAccount).where(OAuthAccount.integration_id == integration.id)
    )
    if account is None:
        return None

    token = decrypt(account.access_token_enc)
    expires = account.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    needs_refresh = expires is not None and expires <= datetime.now(timezone.utc)
    if token and not needs_refresh:
        return token

    refresh_token = decrypt(account.refresh_token_enc)
    if not refresh_token:
        integration.status = IntegrationStatus.EXPIRED.value
        raise IntegrationAuthExpiredError(
            "Your Microsoft connection expired. Reconnect to continue."
        )
    oauth = MicrosoftOAuth()
    bundle = await oauth.refresh(refresh_token)
    await store_tokens(session, integration=integration, bundle=bundle)
    integration.status = IntegrationStatus.CONNECTED.value
    return bundle.access_token


async def resolve_adapters(
    session: AsyncSession, *, organization_id: uuid.UUID
) -> ResolvedAdapters:
    """Produce adapters for the org, honoring mock mode and token refresh."""
    if is_mock_mode():
        return build_adapters(None)

    token = await _valid_access_token(session, organization_id=organization_id)
    goodday = await get_integration(
        session, organization_id=organization_id, provider="goodday"
    )
    goodday_key = None
    if goodday is not None and goodday.settings:
        try:
            goodday_key = json.loads(goodday.settings).get("api_key")
        except json.JSONDecodeError:
            goodday_key = None
    return build_adapters(token, goodday_key=goodday_key)


def read_goodday_key(integration: Integration | None) -> str | None:
    if integration is None or not integration.settings:
        return None
    try:
        return json.loads(integration.settings).get("api_key")
    except json.JSONDecodeError:
        return None