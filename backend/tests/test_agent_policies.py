"""Approval policy tests: READ auto-runs, WRITE always requires approval."""

from __future__ import annotations

from app.agents import policies
from app.tools.base import Tool, ToolContext, ToolKind, ToolResult, ToolRisk


class _ReadTool(Tool):
    name = "search_outlook_emails"
    description = "r"
    kind = ToolKind.READ

    async def run(self, ctx: ToolContext, **arguments):  # pragma: no cover
        return ToolResult(True, "ok", {})


class _WriteTool(Tool):
    name = "create_goodday_task"
    description = "w"
    kind = ToolKind.WRITE
    risk = ToolRisk.MEDIUM

    async def run(self, ctx: ToolContext, **arguments):  # pragma: no cover
        return ToolResult(True, "ok", {})


class _SendEmail(Tool):
    name = "send_email"
    description = "s"
    kind = ToolKind.WRITE
    risk = ToolRisk.HIGH

    async def run(self, ctx: ToolContext, **arguments):  # pragma: no cover
        return ToolResult(True, "ok", {})


def test_read_tools_do_not_require_approval() -> None:
    assert policies.evaluate(_ReadTool()).requires_approval is False


def test_write_tools_require_approval() -> None:
    assert policies.evaluate(_WriteTool()).requires_approval is True


def test_external_side_effects_always_require_approval() -> None:
    assert policies.evaluate(_SendEmail()).requires_approval is True


def test_injection_flagged_forces_approval_on_writes() -> None:
    assert policies.evaluate(_WriteTool(), injection_flagged=True).requires_approval is True