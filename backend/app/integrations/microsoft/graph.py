"""Thin Microsoft Graph HTTP client.

Centralizes Graph calls, auth headers, retries, throttling (429/Retry-After),
and error mapping. No Graph URL is constructed outside this module.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.errors import (
    IntegrationAuthExpiredError,
    IntegrationUnavailableError,
)
from app.core.logging import get_logger

logger = get_logger("app.integrations.microsoft.graph")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_MAX_RETRIES = 3


class MicrosoftGraphClient:
    """Minimal async Graph client with retry + throttle handling."""

    def __init__(self, access_token: str, *, base_url: str = GRAPH_BASE) -> None:
        self._token = access_token
        self._base = base_url
        self._client = httpx.AsyncClient(timeout=30, base_url=base_url)

    async def __aenter__(self) -> "MicrosoftGraphClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.request(
                    method, path, params=params, json=json, headers=self._headers()
                )
            except httpx.HTTPError as exc:
                last_error = exc
                await asyncio.sleep(0.5 * (attempt + 1))
                continue

            if resp.status_code == 401:
                raise IntegrationAuthExpiredError(
                    "Your Outlook/Microsoft connection expired. Reconnect to continue."
                )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "2"))
                logger.warning("Graph throttled; retrying after %ss", retry_after)
                await asyncio.sleep(min(retry_after, 10))
                continue
            if resp.status_code >= 500:
                last_error = IntegrationUnavailableError(
                    "Microsoft Graph is temporarily unavailable."
                )
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                logger.warning("Graph error %s on %s", resp.status_code, path)
                raise IntegrationUnavailableError(
                    "Microsoft Graph rejected the request."
                )
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()

        if isinstance(last_error, Exception):
            if isinstance(last_error, (IntegrationAuthExpiredError, IntegrationUnavailableError)):
                raise last_error
            raise IntegrationUnavailableError(
                "Could not reach Microsoft Graph. Retry shortly."
            ) from last_error
        raise IntegrationUnavailableError("Microsoft Graph request failed.")

    async def get(self, path: str, **params: Any) -> dict[str, Any]:
        clean = {k: v for k, v in params.items() if v is not None}
        return await self.request("GET", path, params=clean or None)

    async def post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("POST", path, json=json)

    async def patch(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("PATCH", path, json=json)

    async def get_me(self) -> dict[str, Any]:
        return await self.get("/me")