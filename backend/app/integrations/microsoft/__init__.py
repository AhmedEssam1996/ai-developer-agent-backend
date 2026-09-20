"""Microsoft Graph integration (Outlook Mail/Calendar, Teams)."""

from app.integrations.microsoft.adapters import (
    MicrosoftCalendarAdapter,
    MicrosoftDirectoryAdapter,
    MicrosoftMailAdapter,
    MicrosoftTeamsAdapter,
)
from app.integrations.microsoft.graph import MicrosoftGraphClient
from app.integrations.microsoft.oauth import MicrosoftOAuth

__all__ = [
    "MicrosoftGraphClient",
    "MicrosoftOAuth",
    "MicrosoftMailAdapter",
    "MicrosoftCalendarAdapter",
    "MicrosoftTeamsAdapter",
    "MicrosoftDirectoryAdapter",
]