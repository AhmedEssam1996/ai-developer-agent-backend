"""READ tools — safe to auto-execute (no external side effects).

These query normalized local data first (fast, tenant-isolated) and fall back
to live adapters for fresher/wider results. They return concise summaries for
the model plus structured ``data`` for the UI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, or_, select

from app.integrations.registry import provider_configured
from app.models.work import CalendarEvent, Email, Message, Task
from app.tools.base import Tool, ToolContext, ToolKind, ToolResult, ToolRisk


def _fmt_email(e: Email) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "subject": e.subject,
        "from": e.sender_name or e.sender_email,
        "from_email": e.sender_email,
        "received_at": e.received_at.isoformat() if e.received_at else None,
        "preview": e.body_preview[:300],
        "priority": e.priority,
        "needs_reply": e.needs_reply,
        "is_important": e.is_important,
    }


class SearchOutlookEmails(Tool):
    name = "search_outlook_emails"
    description = "Search the user's Outlook emails by free-text query and/or sender."
    kind = ToolKind.READ
    risk = ToolRisk.LOW
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Free-text to match in subject/body."},
            "from_email": {"type": "string", "description": "Filter by sender email."},
            "limit": {"type": "integer", "default": 10},
        },
    }

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        query = (arguments.get("query") or "").strip()
        from_email = (arguments.get("from_email") or "").strip().lower()
        try:
            limit = int(arguments.get("limit") or 10)
        except (TypeError, ValueError):
            return ToolResult(False, "limit must be an integer between 1 and 25.", {})
        limit = min(max(limit, 1), 25)

        stmt = select(Email).where(Email.organization_id == ctx.organization_id)
        if query:
            like = f"%{query}%"
            stmt = stmt.where(
                or_(Email.subject.ilike(like), Email.body_preview.ilike(like))
            )
        if from_email:
            stmt = stmt.where(Email.sender_email.ilike(f"%{from_email}%"))
        stmt = stmt.order_by(desc(Email.received_at)).limit(limit)
        rows = list(await ctx.session.scalars(stmt))

        if not rows and provider_configured("outlook") and ctx.adapters and query:
            live = await ctx.adapters.mail.list_messages(search=query, top=limit)
            data = [
                {
                    "subject": m.subject,
                    "from": m.sender_name or m.sender_email,
                    "from_email": m.sender_email,
                    "received_at": m.received_at.isoformat() if m.received_at else None,
                    "preview": m.body_preview[:300],
                }
                for m in live
            ]
            return ToolResult(True, f"Found {len(data)} emails (live search).", {"emails": data})

        return ToolResult(
            True,
            f"Found {len(rows)} emails.",
            {"emails": [_fmt_email(e) for e in rows]},
        )


class GetEmail(Tool):
    name = "get_email"
    description = "Fetch a single Outlook email by its internal id."
    kind = ToolKind.READ
    parameters = {
        "type": "object",
        "properties": {"email_id": {"type": "string"}},
        "required": ["email_id"],
    }

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        email_id = arguments.get("email_id")
        email = await ctx.session.get(Email, _to_uuid(email_id))
        if email is None or email.organization_id != ctx.organization_id:
            return ToolResult(False, "Email not found.", {})
        return ToolResult(True, f"Email: {email.subject}", {"email": _fmt_email(email)})


class SearchCalendar(Tool):
    name = "search_calendar"
    description = "List upcoming calendar events, optionally filtered by text."
    kind = ToolKind.READ
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "days": {"type": "integer", "default": 7},
        },
    }

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        query = (arguments.get("query") or "").strip()
        days = min(int(arguments.get("days") or 7), 30)
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        stmt = (
            select(CalendarEvent)
            .where(
                CalendarEvent.organization_id == ctx.organization_id,
                CalendarEvent.ends_at >= now,
                CalendarEvent.starts_at <= now + timedelta(days=days),
            )
            .order_by(CalendarEvent.starts_at)
            .limit(50)
        )
        if query:
            stmt = stmt.where(CalendarEvent.subject.ilike(f"%{query}%"))
        rows = list(await ctx.session.scalars(stmt))
        events = [
            {
                "id": str(e.id),
                "subject": e.subject,
                "starts_at": e.starts_at.isoformat(),
                "ends_at": e.ends_at.isoformat(),
                "location": e.location,
                "organizer": e.organizer_email,
                "join_url": e.join_url,
            }
            for e in rows
        ]
        return ToolResult(True, f"Found {len(events)} upcoming events.", {"events": events})


class GetCalendarEvent(Tool):
    name = "get_calendar_event"
    description = "Fetch a single calendar event by internal id."
    kind = ToolKind.READ
    parameters = {
        "type": "object",
        "properties": {"event_id": {"type": "string"}},
        "required": ["event_id"],
    }

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        event = await ctx.session.get(CalendarEvent, _to_uuid(arguments.get("event_id")))
        if event is None or event.organization_id != ctx.organization_id:
            return ToolResult(False, "Event not found.", {})
        return ToolResult(
            True,
            f"Event: {event.subject}",
            {
                "event": {
                    "subject": event.subject,
                    "starts_at": event.starts_at.isoformat(),
                    "ends_at": event.ends_at.isoformat(),
                    "location": event.location,
                    "join_url": event.join_url,
                    "preview": event.body_preview[:500],
                }
            },
        )


class SearchTeamsMessages(Tool):
    name = "search_teams_messages"
    description = "Search Microsoft Teams messages by text and/or conversation."
    kind = ToolKind.READ
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "conversation_id": {"type": "string"},
            "limit": {"type": "integer", "default": 15},
        },
    }

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        query = (arguments.get("query") or "").strip()
        conversation_id = (arguments.get("conversation_id") or "").strip()
        limit = min(int(arguments.get("limit") or 15), 40)
        stmt = select(Message).where(Message.organization_id == ctx.organization_id)
        if query:
            stmt = stmt.where(Message.body.ilike(f"%{query}%"))
        if conversation_id:
            stmt = stmt.where(Message.conversation_id == conversation_id)
        stmt = stmt.order_by(desc(Message.sent_at)).limit(limit)
        rows = list(await ctx.session.scalars(stmt))
        messages = [
            {
                "id": str(m.id),
                "conversation": m.conversation_name,
                "conversation_id": m.conversation_id,
                "from": m.sender_name or m.sender_email,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                "body": m.body[:400],
            }
            for m in rows
        ]
        return ToolResult(True, f"Found {len(messages)} messages.", {"messages": messages})


class GetTeamsConversation(Tool):
    name = "get_teams_conversation"
    description = "Retrieve the full messages of a Teams conversation."
    kind = ToolKind.READ
    parameters = {
        "type": "object",
        "properties": {"conversation_id": {"type": "string"}},
        "required": ["conversation_id"],
    }

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        conversation_id = arguments.get("conversation_id") or ""
        stmt = (
            select(Message)
            .where(
                Message.organization_id == ctx.organization_id,
                Message.conversation_id == conversation_id,
            )
            .order_by(Message.sent_at)
            .limit(100)
        )
        rows = list(await ctx.session.scalars(stmt))
        messages = [
            {
                "from": m.sender_name or m.sender_email,
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                "body": m.body[:500],
            }
            for m in rows
        ]
        return ToolResult(True, f"{len(messages)} messages.", {"messages": messages})


class SearchGoodDayTasks(Tool):
    name = "search_goodday_tasks"
    description = "Search GoodDay tasks by text, status or project."
    kind = ToolKind.READ
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "status": {"type": "string"},
            "overdue_only": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "default": 20},
        },
    }

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        query = (arguments.get("query") or "").strip()
        status = (arguments.get("status") or "").strip()
        overdue_only = bool(arguments.get("overdue_only"))
        limit = min(int(arguments.get("limit") or 20), 50)
        stmt = select(Task).where(Task.organization_id == ctx.organization_id)
        if query:
            stmt = stmt.where(or_(Task.title.ilike(f"%{query}%"), Task.description.ilike(f"%{query}%")))
        if status:
            stmt = stmt.where(Task.status == status)
        if overdue_only:
            stmt = stmt.where(Task.is_overdue.is_(True))
        stmt = stmt.order_by(desc(Task.is_overdue), Task.due_at).limit(limit)
        rows = list(await ctx.session.scalars(stmt))
        tasks = [
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "is_overdue": t.is_overdue,
                "assignee": t.assignee_name or t.assignee_email,
                "progress": t.progress,
            }
            for t in rows
        ]
        return ToolResult(True, f"Found {len(tasks)} tasks.", {"tasks": tasks})


class GetGoodDayTask(Tool):
    name = "get_goodday_task"
    description = "Fetch a single GoodDay task by id."
    kind = ToolKind.READ
    parameters = {
        "type": "object",
        "properties": {"task_id": {"type": "string"}},
        "required": ["task_id"],
    }

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        task = await ctx.session.get(Task, _to_uuid(arguments.get("task_id")))
        if task is None or task.organization_id != ctx.organization_id:
            return ToolResult(False, "Task not found.", {})
        return ToolResult(
            True,
            f"Task: {task.title}",
            {
                "task": {
                    "title": task.title,
                    "status": task.status,
                    "priority": task.priority,
                    "due_at": task.due_at.isoformat() if task.due_at else None,
                    "description": task.description[:500],
                    "assignee": task.assignee_name or task.assignee_email,
                }
            },
        )


def _to_uuid(value: Any):
    import uuid

    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return uuid.UUID(int=0)


READ_TOOLS: list[Tool] = [
    SearchOutlookEmails(),
    GetEmail(),
    SearchCalendar(),
    GetCalendarEvent(),
    SearchTeamsMessages(),
    GetTeamsConversation(),
    SearchGoodDayTasks(),
    GetGoodDayTask(),
]