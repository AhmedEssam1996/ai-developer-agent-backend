"""WRITE tools — external side effects, always approval-gated.

These never execute during the agent's automatic loop. The executor records a
pending ``AgentAction`` and the user must approve before ``run`` is invoked.
The ``preview`` method produces the human-readable approval card content.
A "reject all" guard is enforced by policy, not by the tool.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.tools.base import Tool, ToolContext, ToolKind, ToolResult, ToolRisk


class _WriteTool(Tool):
    kind = ToolKind.WRITE
    risk = ToolRisk.MEDIUM

    def preview(self, **arguments: Any) -> str:  # overridden where useful
        return self.description


class CreateGoodDayTask(_WriteTool):
    name = "create_goodday_task"
    description = "Create a task in GoodDay."
    risk = ToolRisk.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "due_at": {"type": "string", "description": "ISO-8601 due date."},
            "assignee_email": {"type": "string"},
            "project_external_id": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
        },
        "required": ["title"],
    }

    def preview(self, **arguments: Any) -> str:
        return f"Create GoodDay task: “{arguments.get('title', '')}”"

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        if ctx.adapters is None:
            return ToolResult(False, "Integrations are not available.", {})
        due = _parse_dt(arguments.get("due_at"))
        result = await ctx.adapters.tasks.create_task(
            title=arguments["title"],
            description=arguments.get("description", ""),
            due_at=due,
            assignee_email=arguments.get("assignee_email"),
            project_external_id=arguments.get("project_external_id"),
            priority=arguments.get("priority", "normal"),
        )
        return ToolResult(True, f"Created task “{arguments['title']}”.", {"result": result})


class UpdateGoodDayTask(_WriteTool):
    name = "update_goodday_task"
    description = "Update an existing GoodDay task (status, due date, priority)."
    risk = ToolRisk.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "task_external_id": {"type": "string"},
            "status": {"type": "string"},
            "priority": {"type": "string"},
            "due_at": {"type": "string"},
            "title": {"type": "string"},
        },
        "required": ["task_external_id"],
    }

    def preview(self, **arguments: Any) -> str:
        changes = {k: v for k, v in arguments.items() if k != "task_external_id"}
        return f"Update GoodDay task {arguments.get('task_external_id')}: {changes}"

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        if ctx.adapters is None:
            return ToolResult(False, "Integrations are not available.", {})
        external_id = arguments.pop("task_external_id")
        if "due_at" in arguments:
            arguments["due_at"] = _parse_dt(arguments["due_at"])
        result = await ctx.adapters.tasks.update_task(external_id, **arguments)
        return ToolResult(True, f"Updated task {external_id}.", {"result": result})


class CreateCalendarEvent(_WriteTool):
    name = "create_calendar_event"
    description = "Create an Outlook calendar event / meeting."
    risk = ToolRisk.MEDIUM
    parameters = {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "start": {"type": "string", "description": "ISO-8601 start."},
            "end": {"type": "string", "description": "ISO-8601 end."},
            "attendees": {"type": "array", "items": {"type": "string"}},
            "body": {"type": "string"},
            "location": {"type": "string"},
        },
        "required": ["subject", "start", "end"],
    }

    def preview(self, **arguments: Any) -> str:
        return f"Create calendar event “{arguments.get('subject', '')}”"

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        if ctx.adapters is None:
            return ToolResult(False, "Integrations are not available.", {})
        start = _parse_dt(arguments["start"])
        end = _parse_dt(arguments["end"])
        if start is None or end is None:
            return ToolResult(False, "Invalid start/end datetime.", {})
        result = await ctx.adapters.calendar.create_event(
            subject=arguments["subject"],
            start=start,
            end=end,
            attendees=arguments.get("attendees"),
            body=arguments.get("body", ""),
            location=arguments.get("location", ""),
        )
        return ToolResult(True, "Calendar event created.", {"result": result})


class DraftEmail(_WriteTool):
    name = "draft_email"
    description = "Create an email draft (does not send)."
    risk = ToolRisk.LOW
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "array", "items": {"type": "string"}},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "cc": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["to", "subject", "body"],
    }

    def preview(self, **arguments: Any) -> str:
        return f"Draft email to {', '.join(arguments.get('to', []))}: “{arguments.get('subject', '')}”"

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        if ctx.adapters is None:
            return ToolResult(False, "Integrations are not available.", {})
        result = await ctx.adapters.mail.create_draft(
            to=arguments["to"],
            subject=arguments["subject"],
            body=arguments["body"],
            cc=arguments.get("cc"),
        )
        return ToolResult(True, "Draft created.", {"result": result})


class SendEmail(_WriteTool):
    name = "send_email"
    description = "Send an email via Outlook. Requires approval."
    risk = ToolRisk.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "array", "items": {"type": "string"}},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "cc": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["to", "subject", "body"],
    }

    def preview(self, **arguments: Any) -> str:
        return (
            f"Send email to {', '.join(arguments.get('to', []))}\n"
            f"Subject: {arguments.get('subject', '')}\n\n{arguments.get('body', '')}"
        )

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        if ctx.adapters is None:
            return ToolResult(False, "Integrations are not available.", {})
        result = await ctx.adapters.mail.send_message(
            to=arguments["to"],
            subject=arguments["subject"],
            body=arguments["body"],
            cc=arguments.get("cc"),
        )
        return ToolResult(True, "Email sent.", {"result": result})


class DraftTeamsMessage(_WriteTool):
    name = "draft_teams_message"
    description = "Prepare a Teams message for review (not sent)."
    risk = ToolRisk.LOW
    parameters = {
        "type": "object",
        "properties": {
            "conversation_id": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["conversation_id", "body"],
    }

    def preview(self, **arguments: Any) -> str:
        return f"Draft Teams message:\n\n{arguments.get('body', '')}"

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        return ToolResult(
            True,
            "Teams message prepared.",
            {"draft": {"conversation_id": arguments["conversation_id"], "body": arguments["body"]}},
        )


class SendTeamsMessage(_WriteTool):
    name = "send_teams_message"
    description = "Send a Microsoft Teams message. Requires approval."
    risk = ToolRisk.HIGH
    parameters = {
        "type": "object",
        "properties": {
            "conversation_id": {"type": "string"},
            "body": {"type": "string"},
        },
        "required": ["conversation_id", "body"],
    }

    def preview(self, **arguments: Any) -> str:
        return (
            f"Send Teams message to conversation {arguments.get('conversation_id')}\n\n"
            f"{arguments.get('body', '')}"
        )

    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult:
        if ctx.adapters is None:
            return ToolResult(False, "Integrations are not available.", {})
        result = await ctx.adapters.teams.send_message(
            conversation_id=arguments["conversation_id"], body=arguments["body"]
        )
        return ToolResult(True, "Teams message sent.", {"result": result})


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


WRITE_TOOLS: list[Tool] = [
    CreateGoodDayTask(),
    UpdateGoodDayTask(),
    CreateCalendarEvent(),
    DraftEmail(),
    SendEmail(),
    DraftTeamsMessage(),
    SendTeamsMessage(),
]