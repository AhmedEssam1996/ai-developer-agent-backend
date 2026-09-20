"""Synthetic, clearly-labeled development adapters.

All returned records include a ``raw`` marker ``{"_mock": True}`` and realistic
shapes so the UI can be built end-to-end. These are only wired in ``mock`` mode.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.integrations.base import (
    CalendarAdapter,
    DirectoryAdapter,
    MailAdapter,
    NormalizedCalendarEvent,
    NormalizedEmail,
    NormalizedMessage,
    NormalizedPerson,
    NormalizedProject,
    NormalizedTask,
    TaskAdapter,
    TeamsAdapter,
)

_NOW = datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_mock_{uuid.uuid4().hex[:12]}"


_DIRECTORY = [
    NormalizedPerson(external_id="p_mohamed", email="mohamed@example.com", display_name="Mohamed Ali"),
    NormalizedPerson(external_id="p_sara", email="sara@example.com", display_name="Sara Ibrahim"),
    NormalizedPerson(external_id="p_omar", email="omar@example.com", display_name="Omar Hassan"),
    NormalizedPerson(external_id="p_laila", email="laila@example.com", display_name="Laila Nasser"),
]


class _Base:
    provider = "mock"
    is_mock = True

    async def health(self) -> bool:
        return True


def _mock_emails() -> list[NormalizedEmail]:
    return [
        NormalizedEmail(
            external_id="mock_email_api_docs",
            subject="Please send the updated API documentation by Wednesday",
            body_preview=(
                "Ahmed, please send the updated API documentation by Wednesday so the "
                "client team can review before the milestone."
            ),
            sender_email="mohamed@example.com",
            sender_name="Mohamed Ali",
            to_recipients=["ahmed@example.com"],
            received_at=_NOW - timedelta(hours=2),
            is_read=False,
            has_attachments=False,
            importance="high",
            raw={"_mock": True},
        ),
        NormalizedEmail(
            external_id="mock_email_proposal",
            subject="Client proposal — final pricing review",
            body_preview=(
                "Here is the final pricing proposal. We need your response before "
                "Thursday's steering call."
            ),
            sender_email="laila@example.com",
            sender_name="Laila Nasser",
            to_recipients=["ahmed@example.com"],
            received_at=_NOW - timedelta(hours=5),
            is_read=False,
            importance="high",
            raw={"_mock": True},
        ),
        NormalizedEmail(
            external_id="mock_email_escalation",
            subject="Project X — escalation on integration testing",
            body_preview="We are blocked on the integration environment. Requesting prioritization.",
            sender_email="omar@example.com",
            sender_name="Omar Hassan",
            to_recipients=["ahmed@example.com"],
            received_at=_NOW - timedelta(days=1),
            is_read=True,
            importance="normal",
            raw={"_mock": True},
        ),
    ]


class MockMailAdapter(_Base, MailAdapter):
    provider = "outlook"

    async def list_messages(
        self, *, since: datetime | None = None, top: int = 50, search: str | None = None
    ) -> list[NormalizedEmail]:
        samples = _mock_emails()
        if search:
            s = search.lower()
            samples = [
                e
                for e in samples
                if s in e.subject.lower()
                or s in e.body_preview.lower()
                or s in e.sender_email.lower()
            ]
        return samples[:top]

    async def get_message(self, external_id: str) -> NormalizedEmail | None:
        for m in await self.list_messages(top=100):
            if m.external_id == external_id:
                return m
        return None

    async def send_message(
        self, *, to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> dict[str, Any]:
        return {"status": "sent", "mock": True, "to": to, "subject": subject}

    async def create_draft(
        self, *, to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> dict[str, Any]:
        return {"status": "draft", "mock": True, "id": _id("draft"), "to": to}


class MockCalendarAdapter(_Base, CalendarAdapter):
    provider = "outlook"

    async def list_events(
        self, *, start: datetime | None = None, end: datetime | None = None, top: int = 50
    ) -> list[NormalizedCalendarEvent]:
        return [
            NormalizedCalendarEvent(
                external_id="mock_event_projectx",
                subject="Project X — Steering Sync",
                body_preview="Agenda: integration testing, risks, timeline.",
                starts_at=_NOW + timedelta(hours=3),
                ends_at=_NOW + timedelta(hours=4),
                location="Microsoft Teams",
                organizer_email="ahmed@example.com",
                attendees=[{"email": p.email, "name": p.display_name} for p in _DIRECTORY[:3]],
                is_online_meeting=True,
                join_url="https://teams.microsoft.com/l/meetup-join/mock",
                raw={"_mock": True},
            ),
            NormalizedCalendarEvent(
                external_id="mock_event_teamsync",
                subject="Daily Team Sync",
                body_preview="Standup and blockers.",
                starts_at=_NOW + timedelta(hours=5, minutes=30),
                ends_at=_NOW + timedelta(hours=6),
                location="Microsoft Teams",
                organizer_email="sara@example.com",
                attendees=[{"email": p.email, "name": p.display_name} for p in _DIRECTORY],
                is_online_meeting=True,
                join_url="https://teams.microsoft.com/l/meetup-join/mock2",
                raw={"_mock": True},
            ),
        ][:top]

    async def get_event(self, external_id: str) -> NormalizedCalendarEvent | None:
        for e in await self.list_events():
            if e.external_id == external_id:
                return e
        return None

    async def create_event(
        self,
        *,
        subject: str,
        start: datetime,
        end: datetime,
        attendees: list[str] | None = None,
        body: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        return {"status": "created", "mock": True, "id": _id("event"), "subject": subject}


class MockTeamsAdapter(_Base, TeamsAdapter):
    provider = "teams"

    async def list_messages(
        self, *, since: datetime | None = None, top: int = 50, search: str | None = None
    ) -> list[NormalizedMessage]:
        samples = [
            NormalizedMessage(
                external_id="mock_msg_1",
                conversation_id="mock_chat_projectx",
                conversation_name="Project X",
                sender_email="mohamed@example.com",
                sender_name="Mohamed Ali",
                body="I'll send the API documentation update by Wednesday.",
                direction="inbound",
                sent_at=_NOW - timedelta(hours=3),
                is_mention=True,
                raw={"_mock": True},
            ),
            NormalizedMessage(
                external_id="mock_msg_2",
                conversation_id="mock_chat_projectx",
                conversation_name="Project X",
                sender_email="sara@example.com",
                sender_name="Sara Ibrahim",
                body="Design review is pending — waiting on the latest mockups.",
                direction="inbound",
                sent_at=_NOW - timedelta(hours=6),
                raw={"_mock": True},
            ),
        ]
        if search:
            s = search.lower()
            samples = [m for m in samples if s in m.body.lower() or s in m.sender_name.lower()]
        return samples[:top]

    async def get_conversation(self, conversation_id: str) -> list[NormalizedMessage]:
        return [m for m in await self.list_messages() if m.conversation_id == conversation_id]

    async def send_message(
        self, *, conversation_id: str, body: str, mentions: list[str] | None = None
    ) -> dict[str, Any]:
        return {"status": "sent", "mock": True, "id": _id("msg"), "conversation_id": conversation_id}


class MockTaskAdapter(_Base, TaskAdapter):
    provider = "goodday"

    async def list_projects(self) -> list[NormalizedProject]:
        return [
            NormalizedProject(external_id="mock_proj_x", name="Project X", description="Client platform"),
            NormalizedProject(external_id="mock_proj_internal", name="Internal Ops", description=""),
        ]

    async def list_tasks(
        self,
        *,
        project_external_id: str | None = None,
        search: str | None = None,
        top: int = 100,
    ) -> list[NormalizedTask]:
        tasks = [
            NormalizedTask(
                external_id="mock_task_api_docs",
                title="Finish API documentation",
                description="Update the API reference and publish for client review.",
                status="open",
                priority="high",
                due_at=_NOW - timedelta(days=1),
                assignee_email="ahmed@example.com",
                assignee_name="Ahmed",
                project_external_id="mock_proj_x",
                project_name="Project X",
                progress=20,
                raw={"_mock": True},
            ),
            NormalizedTask(
                external_id="mock_task_dbtest",
                title="Regression test database migration",
                description="Validate the migration against staging.",
                status="in_progress",
                priority="normal",
                due_at=_NOW + timedelta(days=2),
                assignee_email="omar@example.com",
                assignee_name="Omar Hassan",
                project_external_id="mock_proj_x",
                project_name="Project X",
                progress=60,
                raw={"_mock": True},
            ),
            NormalizedTask(
                external_id="mock_task_design",
                title="Approve settings redesign",
                description="Review and approve the design handoff.",
                status="blocked",
                priority="normal",
                due_at=_NOW + timedelta(days=3),
                assignee_email="sara@example.com",
                assignee_name="Sara Ibrahim",
                project_external_id="mock_proj_internal",
                project_name="Internal Ops",
                raw={"_mock": True},
            ),
        ]
        if project_external_id:
            tasks = [t for t in tasks if t.project_external_id == project_external_id]
        if search:
            s = search.lower()
            tasks = [t for t in tasks if s in t.title.lower() or s in (t.description or "").lower()]
        return tasks[:top]

    async def get_task(self, external_id: str) -> NormalizedTask | None:
        for t in await self.list_tasks():
            if t.external_id == external_id:
                return t
        return None

    async def create_task(
        self,
        *,
        title: str,
        description: str = "",
        due_at: datetime | None = None,
        assignee_email: str | None = None,
        project_external_id: str | None = None,
        priority: str = "normal",
    ) -> dict[str, Any]:
        return {
            "status": "created",
            "mock": True,
            "id": _id("task"),
            "title": title,
            "assignee_email": assignee_email,
        }

    async def update_task(self, external_id: str, **fields: Any) -> dict[str, Any]:
        return {"status": "updated", "mock": True, "id": external_id, "applied": fields}


class MockDirectoryAdapter(_Base, DirectoryAdapter):
    provider = "outlook"

    async def list_people(self, *, search: str | None = None) -> list[NormalizedPerson]:
        if search:
            s = search.lower()
            return [p for p in _DIRECTORY if s in p.display_name.lower() or s in p.email.lower()]
        return list(_DIRECTORY)