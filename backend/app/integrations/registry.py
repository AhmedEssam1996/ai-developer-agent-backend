"""Integration registry.

Resolves the correct adapter for the active ``INTEGRATION_MODE``. This is the
single place that decides between live adapters and the isolated development
adapter, so no business logic ever branches on provider credentials.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.errors import IntegrationNotConfiguredError
from app.integrations.base import (
    CalendarAdapter,
    DirectoryAdapter,
    MailAdapter,
    TaskAdapter,
    TeamsAdapter,
)

PROVIDER_DISPLAY = {
    "outlook": ("Microsoft Outlook", "Email, calendar and contacts via Microsoft Graph."),
    "teams": ("Microsoft Teams", "Chats and channel messages via Microsoft Graph."),
    "goodday": ("GoodDay", "Projects and tasks via the GoodDay API."),
}

SUPPORTED_PROVIDERS = tuple(PROVIDER_DISPLAY.keys())


@dataclass
class ResolvedAdapters:
    mail: MailAdapter
    calendar: CalendarAdapter
    teams: TeamsAdapter
    tasks: TaskAdapter
    directory: DirectoryAdapter
    source: str  # "live" | "mock"
    is_mock: bool


def is_mock_mode() -> bool:
    return settings.integration_mode == "mock"


def _build_mock() -> ResolvedAdapters:
    from app.integrations.mock import (
        MockCalendarAdapter,
        MockDirectoryAdapter,
        MockMailAdapter,
        MockTaskAdapter,
        MockTeamsAdapter,
    )

    return ResolvedAdapters(
        mail=MockMailAdapter(),
        calendar=MockCalendarAdapter(),
        teams=MockTeamsAdapter(),
        tasks=MockTaskAdapter(),
        directory=MockDirectoryAdapter(),
        source="mock",
        is_mock=True,
    )


def _require_microsoft() -> None:
    if not settings.microsoft_configured:
        raise IntegrationNotConfiguredError(
            "Microsoft is not configured. Add MICROSOFT_CLIENT_ID and "
            "MICROSOFT_CLIENT_SECRET, or set INTEGRATION_MODE=mock for local development."
        )


def build_adapters(access_token: str | None, *, goodday_key: str | None = None) -> ResolvedAdapters:
    """Build the adapter set for the active mode.

    In ``mock`` mode the token/key are ignored. In ``live`` mode a valid token
    is required for Microsoft-backed adapters.
    """
    if is_mock_mode():
        return _build_mock()

    _require_microsoft()
    if not access_token:
        raise IntegrationNotConfiguredError(
            "No Microsoft access token available. Connect Outlook first."
        )

    from app.integrations.goodday import GoodDayTaskAdapter
    from app.integrations.microsoft import (
        MicrosoftCalendarAdapter,
        MicrosoftDirectoryAdapter,
        MicrosoftMailAdapter,
        MicrosoftTeamsAdapter,
    )

    return ResolvedAdapters(
        mail=MicrosoftMailAdapter(access_token),
        calendar=MicrosoftCalendarAdapter(access_token),
        teams=MicrosoftTeamsAdapter(access_token),
        tasks=GoodDayTaskAdapter(api_key=goodday_key),
        directory=MicrosoftDirectoryAdapter(access_token),
        source="live",
        is_mock=False,
    )


def provider_configured(provider: str) -> bool:
    """Whether the provider has credentials (independent of connection state)."""
    if is_mock_mode():
        return True
    if provider in ("outlook", "teams"):
        return settings.microsoft_configured
    if provider == "goodday":
        return settings.goodday_configured
    return False


def display_name(provider: str) -> str:
    return PROVIDER_DISPLAY.get(provider, (provider.title(), ""))[0]


def description(provider: str) -> str:
    return PROVIDER_DISPLAY.get(provider, (provider.title(), ""))[1]