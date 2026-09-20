"""Microsoft Graph adapters that normalize Graph payloads into internal DTOs.

Only this module (and ``graph.py``/``oauth.py``) knows Graph's schema. Each
adapter receives a ready-to-use access token resolved by the integration
service (which handles refresh + encryption).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.integrations.base import (
    CalendarAdapter,
    DirectoryAdapter,
    MailAdapter,
    MailAdapter as _MailAdapter,  # noqa: F401 (kept explicit)
    NormalizedCalendarEvent,
    NormalizedEmail,
    NormalizedMessage,
    NormalizedPerson,
    TeamsAdapter,
)
from app.integrations.microsoft.graph import MicrosoftGraphClient

logger = get_logger("app.integrations.microsoft.adapters")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _preview(body: dict[str, Any] | None, limit: int = 400) -> str:
    if not body:
        return ""
    content = (body.get("content") or "").strip()
    # Graph returns HTML for emails; keep a lightweight textual preview.
    text = content.replace("<br>", "\n").replace("</p>", "\n")
    if "<" in text:
        import re

        text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    return text[:limit]


class _GraphBacked:
    def __init__(self, access_token: str) -> None:
        self._token = access_token

    def _client(self) -> MicrosoftGraphClient:
        return MicrosoftGraphClient(self._token)

    async def health(self) -> bool:
        try:
            async with self._client() as client:
                await client.get_me()
            return True
        except Exception:  # pragma: no cover - network dependent
            return False


class MicrosoftMailAdapter(_GraphBacked, MailAdapter):
    provider = "outlook"

    async def list_messages(
        self, *, since: datetime | None = None, top: int = 50, search: str | None = None
    ) -> list[NormalizedEmail]:
        params: dict[str, Any] = {
            "$top": top,
            "$orderby": "receivedDateTime desc",
            "$select": (
                "id,subject,bodyPreview,body,from,toRecipients,ccRecipients,"
                "receivedDateTime,isRead,hasAttachments,importance,conversationId,webLink"
            ),
        }
        if since:
            iso = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            params["$filter"] = f"receivedDateTime ge {iso}"
        if search:
            params["$search"] = f'"{search}"'
        async with self._client() as client:
            data = await client.get("/me/messages", **params)
        return [self._normalize(m) for m in data.get("value", [])]

    async def get_message(self, external_id: str) -> NormalizedEmail | None:
        async with self._client() as client:
            try:
                data = await client.get(f"/me/messages/{external_id}")
            except Exception:
                return None
        return self._normalize(data)

    async def send_message(
        self, *, to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> dict[str, Any]:
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": a}} for a in to],
                "ccRecipients": [{"emailAddress": {"address": a}} for a in (cc or [])],
            }
        }
        async with self._client() as client:
            await client.post("/me/sendMail", json=payload)
        return {"status": "sent", "to": to, "subject": subject}

    async def create_draft(
        self, *, to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> dict[str, Any]:
        payload = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": a}} for a in to],
            "ccRecipients": [{"emailAddress": {"address": a}} for a in (cc or [])],
        }
        async with self._client() as client:
            data = await client.post("/me/messages", json=payload)
        return {"status": "draft", "id": data.get("id"), "to": to}

    @staticmethod
    def _normalize(msg: dict[str, Any]) -> NormalizedEmail:
        sender = (msg.get("from") or {}).get("emailAddress", {})
        return NormalizedEmail(
            external_id=msg.get("id", ""),
            subject=msg.get("subject", "") or "",
            body_preview=msg.get("bodyPreview", "") or _preview(msg.get("body")),
            body_html=(msg.get("body") or {}).get("content"),
            sender_email=sender.get("address", "") or "",
            sender_name=sender.get("name", "") or "",
            to_recipients=[
                (r.get("emailAddress") or {}).get("address", "")
                for r in msg.get("toRecipients", [])
            ],
            cc_recipients=[
                (r.get("emailAddress") or {}).get("address", "")
                for r in msg.get("ccRecipients", [])
            ],
            received_at=_parse_dt(msg.get("receivedDateTime")),
            is_read=bool(msg.get("isRead")),
            has_attachments=bool(msg.get("hasAttachments")),
            importance=msg.get("importance", "normal"),
            thread_id=msg.get("conversationId"),
            web_link=msg.get("webLink"),
            raw=msg,
        )


class MicrosoftCalendarAdapter(_GraphBacked, CalendarAdapter):
    provider = "outlook"

    async def list_events(
        self, *, start: datetime | None = None, end: datetime | None = None, top: int = 50
    ) -> list[NormalizedCalendarEvent]:
        params: dict[str, Any] = {
            "$top": top,
            "$orderby": "start/dateTime",
            "$select": (
                "id,subject,bodyPreview,start,end,isAllDay,location,organizer,"
                "attendees,isOnlineMeeting,onlineMeeting,responseStatus,webLink"
            ),
        }
        start = start or datetime.now(timezone.utc)
        if end is None:
            from datetime import timedelta

            end = start + timedelta(days=14)
        params["startDateTime"] = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        params["endDateTime"] = end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        async with self._client() as client:
            data = await client.get("/me/calendarView", **params)
        return [self._normalize(e) for e in data.get("value", [])]

    async def get_event(self, external_id: str) -> NormalizedCalendarEvent | None:
        async with self._client() as client:
            try:
                data = await client.get(f"/me/events/{external_id}")
            except Exception:
                return None
        return self._normalize(data)

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
        payload = {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "start": {"dateTime": start.astimezone(timezone.utc).isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.astimezone(timezone.utc).isoformat(), "timeZone": "UTC"},
            "location": {"displayName": location},
            "attendees": [
                {"emailAddress": {"address": a}, "type": "required"} for a in (attendees or [])
            ],
        }
        async with self._client() as client:
            data = await client.post("/me/events", json=payload)
        return {"status": "created", "id": data.get("id"), "subject": subject}

    @staticmethod
    def _normalize(evt: dict[str, Any]) -> NormalizedCalendarEvent:
        start = _parse_dt((evt.get("start") or {}).get("dateTime"))
        end = _parse_dt((evt.get("end") or {}).get("dateTime"))
        online = evt.get("onlineMeeting") or {}
        return NormalizedCalendarEvent(
            external_id=evt.get("id", ""),
            subject=evt.get("subject", "") or "",
            body_preview=evt.get("bodyPreview", "") or "",
            starts_at=start,
            ends_at=end,
            is_all_day=bool(evt.get("isAllDay")),
            location=((evt.get("location") or {}).get("displayName") or ""),
            organizer_email=((evt.get("organizer") or {}).get("emailAddress") or {}).get(
                "address", ""
            ),
            attendees=[
                {
                    "email": ((a.get("emailAddress") or {}).get("address")),
                    "name": ((a.get("emailAddress") or {}).get("name")),
                    "status": (a.get("status") or {}).get("response"),
                }
                for a in evt.get("attendees", [])
            ],
            is_online_meeting=bool(evt.get("isOnlineMeeting")),
            join_url=online.get("joinUrl"),
            response_status=((evt.get("responseStatus") or {}).get("response") or "accepted"),
            web_link=evt.get("webLink"),
            raw=evt,
        )


class MicrosoftTeamsAdapter(_GraphBacked, TeamsAdapter):
    provider = "teams"

    async def list_messages(
        self, *, since: datetime | None = None, top: int = 50, search: str | None = None
    ) -> list[NormalizedMessage]:
        # Graph: list recent chats, then fetch messages for each. We keep this
        # bounded to avoid heavy fan-out on sync.
        async with self._client() as client:
            chats = await client.get(
                "/me/chats",
                **{"$top": min(top, 20), "$expand": "members"},
            )
            results: list[NormalizedMessage] = []
            for chat in chats.get("value", []):
                chat_id = chat.get("id")
                if not chat_id:
                    continue
                try:
                    msgs = await client.get(f"/me/chats/{chat_id}/messages", **{"$top": 20})
                except Exception:
                    continue
                for m in msgs.get("value", []):
                    norm = self._normalize(m, chat_id, chat.get("topic", ""))
                    if norm:
                        if since and norm.sent_at and norm.sent_at < since:
                            continue
                        if search and search.lower() not in norm.body.lower():
                            continue
                        results.append(norm)
        return results[:top]

    async def get_conversation(self, conversation_id: str) -> list[NormalizedMessage]:
        async with self._client() as client:
            msgs = await client.get(
                f"/me/chats/{conversation_id}/messages", **{"$top": 50}
            )
        out: list[NormalizedMessage] = []
        for m in msgs.get("value", []):
            norm = self._normalize(m, conversation_id, "")
            if norm:
                out.append(norm)
        return out

    async def send_message(
        self, *, conversation_id: str, body: str, mentions: list[str] | None = None
    ) -> dict[str, Any]:
        payload = {"body": {"contentType": "text", "content": body}}
        async with self._client() as client:
            data = await client.post(f"/me/chats/{conversation_id}/messages", json=payload)
        return {"status": "sent", "id": data.get("id"), "conversation_id": conversation_id}

    @staticmethod
    def _normalize(msg: dict[str, Any], chat_id: str, topic: str) -> NormalizedMessage | None:
        msg_id = msg.get("id")
        if not msg_id:
            return None
        from_user = (msg.get("from") or {}).get("user") or {}
        body = (msg.get("body") or {}).get("content", "") or ""
        return NormalizedMessage(
            external_id=msg_id,
            conversation_id=chat_id,
            conversation_name=topic or "",
            sender_email=from_user.get("email") or "",
            sender_name=from_user.get("displayName") or "",
            body=body,
            direction="inbound",
            sent_at=_parse_dt(msg.get("createdDateTime")),
            is_mention="@mention" in str(msg.get("mentions", [])).lower(),
            web_link=msg.get("webUrl"),
            raw=msg,
        )


class MicrosoftDirectoryAdapter(_GraphBacked, DirectoryAdapter):
    provider = "outlook"

    async def list_people(self, *, search: str | None = None) -> list[NormalizedPerson]:
        params: dict[str, Any] = {"$top": 50}
        path = "/me/people"
        if search:
            params["$search"] = f'"{search}"'
        async with self._client() as client:
            data = await client.get(path, **params)
        people: list[NormalizedPerson] = []
        for p in data.get("value", []):
            emails = p.get("scoredEmailAddresses") or []
            address = emails[0].get("address") if emails else p.get("userPrincipalName")
            people.append(
                NormalizedPerson(
                    external_id=p.get("id", ""),
                    email=address or "",
                    display_name=p.get("displayName", "") or "",
                )
            )
        return people