"""Integration layer.

Every external provider is reached through an *adapter* that returns the
normalized models defined here. Business logic and the AI agent depend only on
these interfaces — never on provider SDKs or raw JSON.

Adapters:

* ``microsoft`` — Outlook Mail + Calendar and Teams via Microsoft Graph.
* ``goodday``   — GoodDay projects/tasks via REST.
* ``mock``      — isolated development adapter (clearly labeled synthetic data).

Selection is controlled by ``settings.integration_mode`` (live|mock) through
``app.integrations.registry``.
"""

from app.integrations.base import (
    CalendarAdapter,
    DirectoryAdapter,
    MailAdapter,
    TaskAdapter,
    TeamsAdapter,
)

__all__ = [
    "MailAdapter",
    "CalendarAdapter",
    "TeamsAdapter",
    "TaskAdapter",
    "DirectoryAdapter",
]