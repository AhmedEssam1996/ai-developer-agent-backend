"""GoodDay REST client.

Centralizes GoodDay HTTP calls, API-key auth, retries and error mapping. The
exact endpoints below match GoodDay's v1 API surface; all GoodDay-specific
model shapes are normalized in ``adapters.py``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import (
    IntegrationAuthExpiredError,
    IntegrationNotConfiguredError,
    IntegrationUnavailableError,
)
from app.core.logging import get_logger

logger = get_logger("app.integrations.goodday.client")

_MAX_RETRIES = 3


class GoodDayClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.goodday_api_key
        self._base = settings.goodday_base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30)

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def __aenter__(self) -> "GoodDayClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
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
    ) -> Any:
        if not self.configured:
            raise IntegrationNotConfiguredError(
                "GoodDay is not configured. Set GOODDAY_API_KEY."
            )
        url = f"{self._base}{path}"
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.request(
                    method, url, params=params, json=json, headers=self._headers()
                )
            except httpx.HTTPError as exc:
                last_error = exc
                await asyncio.sleep(0.5 * (attempt + 1))
                continue

            if resp.status_code in (401, 403):
                raise IntegrationAuthExpiredError(
                    "Your GoodDay connection is invalid. Reconnect to continue."
                )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "2"))
                await asyncio.sleep(min(retry_after, 10))
                continue
            if resp.status_code >= 500:
                last_error = IntegrationUnavailableError(
                    "GoodDay is temporarily unavailable."
                )
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                logger.warning("GoodDay error %s on %s", resp.status_code, path)
                raise IntegrationUnavailableError("GoodDay rejected the request.")
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()

        if isinstance(last_error, Exception):
            if isinstance(last_error, (IntegrationAuthExpiredError, IntegrationUnavailableError)):
                raise last_error
            raise IntegrationUnavailableError(
                "Could not reach GoodDay. Retry shortly."
            ) from last_error
        raise IntegrationUnavailableError("GoodDay request failed.")

    async def get(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        return await self.request("GET", path, params=clean or None)

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self.request("POST", path, json=json)

    async def patch(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self.request("PATCH", path, json=json)

    async def health(self) -> bool:
        try:
            await self.get("/projects", limit=1)
            return True
        except Exception:  # pragma: no cover
            return False