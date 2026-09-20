"""Isolated development (mock) adapter.

Used only when ``INTEGRATION_MODE=mock``. It returns clearly-labeled synthetic
data so the app can be developed and demoed without real credentials. Every
record carries ``is_mock=True`` markers and the registry reports it, so the UI
can display a persistent "Development data" badge.

This module is never imported by production adapter paths.
"""

from app.integrations.mock.adapters import (
    MockCalendarAdapter,
    MockDirectoryAdapter,
    MockMailAdapter,
    MockTaskAdapter,
    MockTeamsAdapter,
)

__all__ = [
    "MockMailAdapter",
    "MockCalendarAdapter",
    "MockTeamsAdapter",
    "MockTaskAdapter",
    "MockDirectoryAdapter",
]