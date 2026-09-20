"""Microsoft identity OAuth (authorization code + refresh)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.errors import (
    IntegrationAuthExpiredError,
    IntegrationNotConfiguredError,
    IntegrationUnavailableError,
)
from app.core.logging import get_logger
from app.integrations.base import TokenBundle

logger = get_logger("app.integrations.microsoft.oauth")

# Least-privilege scopes. Mail/Calendar and Teams chat.
DEFAULT_SCOPES = [
    "offline_access",
    "User.Read",
    "Mail.Read",
    "Mail.Send",
    "Calendars.ReadWrite",
    "Chat.Read",
    "ChatMessage.Send",
]


class MicrosoftOAuth:
    """Handles the authorization-code flow and token refresh."""

    def __init__(self) -> None:
        self.client_id = settings.microsoft_client_id
        self.client_secret = settings.microsoft_client_secret
        self.redirect_uri = settings.microsoft_redirect_uri
        self.authority = settings.microsoft_authority()

    @property
    def configured(self) -> bool:
        return settings.microsoft_configured

    def _require_config(self) -> None:
        if not self.configured:
            raise IntegrationNotConfiguredError(
                "Microsoft integration is not configured. Set MICROSOFT_CLIENT_ID "
                "and MICROSOFT_CLIENT_SECRET."
            )

    def generate_state(self) -> str:
        return secrets.token_urlsafe(24)

    def build_authorize_url(self, *, state: str, scopes: list[str] | None = None) -> str:
        self._require_config()
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": " ".join(scopes or DEFAULT_SCOPES),
            "state": state,
            "prompt": "select_account",
        }
        return f"{self.authority}/oauth2/v2.0/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> TokenBundle:
        self._require_config()
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(DEFAULT_SCOPES),
        }
        return await self._token_request(data)

    async def refresh(self, refresh_token: str) -> TokenBundle:
        self._require_config()
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(DEFAULT_SCOPES),
        }
        return await self._token_request(data)

    async def _token_request(self, data: dict) -> TokenBundle:
        url = f"{self.authority}/oauth2/v2.0/token"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, data=data)
        except httpx.HTTPError as exc:
            raise IntegrationUnavailableError(
                "Could not reach Microsoft sign-in. Retry shortly."
            ) from exc

        if resp.status_code >= 400:
            payload = _safe_json(resp)
            error = payload.get("error", "token_error")
            logger.warning("Microsoft token request failed: %s", error)
            if error in {"invalid_grant", "interaction_required"}:
                raise IntegrationAuthExpiredError(
                    "Your Microsoft connection expired. Reconnect to continue."
                )
            raise IntegrationUnavailableError("Microsoft sign-in rejected the request.")

        payload = resp.json()
        expires_in = int(payload.get("expires_in", 3600))
        return TokenBundle(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            scope=payload.get("scope", ""),
            token_type=payload.get("token_type", "Bearer"),
        )


def _safe_json(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {}