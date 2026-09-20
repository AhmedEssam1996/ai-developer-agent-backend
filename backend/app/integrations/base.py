"""Provider-agnostic integration interfaces and normalized DTOs.

Adapters convert provider payloads into these DTOs. Nothing above the
integration layer should know about Microsoft Graph or GoodDay schemas.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NormalizedEmail:
    external_id: str
    subject: str = ""
    body_preview: str = ""
    body_html: str | None = None
    sender_email: str = ""
    sender_name: str = ""
    to_recipients: list[str] = field(default_factory=list)
    cc_recipients: list[str] = field(default_factory=list)
    received_at: datetime | None = None
    is_read: bool = False
    has_attachments: bool = False
    importance: str = "normal"
    thread_id: str | None = None
    web_link: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedCalendarEvent:
    external_id: str
    subject: str = ""
    body_preview: str = ""
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_all_day: bool = False
    location: str = ""
    organizer_email: str = ""
    attendees: list[dict[str, Any]] = field(default_factory=list)
    is_online_meeting: bool = False
    join_url: str | None = None
    response_status: str = "accepted"
    web_link: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedMessage:
    external_id: str
    conversation_id: str = ""
    conversation_name: str = ""
    sender_email: str = ""
    sender_name: str = ""
    body: str = ""
    direction: str = "inbound"
    sent_at: datetime | None = None
    is_mention: bool = False
    web_link: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedTask:
    external_id: str
    title: str = ""
    description: str = ""
    status: str = "open"
    priority: str = "normal"
    due_at: datetime | None = None
    completed_at: datetime | None = None
    assignee_email: str | None = None
    assignee_name: str | None = None
    project_external_id: str | None = None
    project_name: str | None = None
    progress: int = 0
    web_link: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedProject:
    external_id: str
    name: str = ""
    description: str = ""


@dataclass
class NormalizedPerson:
    external_id: str
    email: str = ""
    display_name: str = ""


@dataclass
class TokenBundle:
    """OAuth token bundle returned by the authorization-code exchange."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scope: str = ""
    token_type: str = "Bearer"


class IntegrationAdapter(ABC):
    """Common lifecycle for an integration adapter."""

    provider: str = "unknown"

    @abstractmethod
    async def health(self) -> bool:
        """Return ``True`` if the adapter is usable right now."""


class MailAdapter(IntegrationAdapter):
    @abstractmethod
    async def list_messages(
        self, *, since: datetime | None = None, top: int = 50, search: str | None = None
    ) -> list[NormalizedEmail]: ...

    @abstractmethod
    async def get_message(self, external_id: str) -> NormalizedEmail | None: ...

    @abstractmethod
    async def send_message(
        self, *, to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def create_draft(
        self, *, to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> dict[str, Any]: ...


class CalendarAdapter(IntegrationAdapter):
    @abstractmethod
    async def list_events(
        self, *, start: datetime | None = None, end: datetime | None = None, top: int = 50
    ) -> list[NormalizedCalendarEvent]: ...

    @abstractmethod
    async def get_event(self, external_id: str) -> NormalizedCalendarEvent | None: ...

    @abstractmethod
    async def create_event(
        self,
        *,
        subject: str,
        start: datetime,
        end: datetime,
        attendees: list[str] | None = None,
        body: str = "",
        location: str = "",
    ) -> dict[str, Any]: ...


class TeamsAdapter(IntegrationAdapter):
    @abstractmethod
    async def list_messages(
        self, *, since: datetime | None = None, top: int = 50, search: str | None = None
    ) -> list[NormalizedMessage]: ...

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> list[NormalizedMessage]: ...

    @abstractmethod
    async def send_message(
        self, *, conversation_id: str, body: str, mentions: list[str] | None = None
    ) -> dict[str, Any]: ...


class TaskAdapter(IntegrationAdapter):
    @abstractmethod
    async def list_projects(self) -> list[NormalizedProject]: ...

    @abstractmethod
    async def list_tasks(
        self,
        *,
        project_external_id: str | None = None,
        search: str | None = None,
        top: int = 100,
    ) -> list[NormalizedTask]: ...

    @abstractmethod
    async def get_task(self, external_id: str) -> NormalizedTask | None: ...

    @abstractmethod
    async def create_task(
        self,
        *,
        title: str,
        description: str = "",
        due_at: datetime | None = None,
        assignee_email: str | None = None,
        project_external_id: str | None = None,
        priority: str = "normal",
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def update_task(self, external_id: str, **fields: Any) -> dict[str, Any]: ...


class DirectoryAdapter(IntegrationAdapter):
    @abstractmethod
    async def list_people(self, *, search: str | None = None) -> list[NormalizedPerson]: ...