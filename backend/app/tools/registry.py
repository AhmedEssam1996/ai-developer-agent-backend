"""Tool registry: lookup by name + schema export for the model."""

from __future__ import annotations

from app.ai.provider import ToolSchema
from app.tools.base import Tool, ToolKind
from app.tools.read_tools import READ_TOOLS
from app.tools.write_tools import WRITE_TOOLS

_TOOLS: dict[str, Tool] = {tool.name: tool for tool in (*READ_TOOLS, *WRITE_TOOLS)}


def get_tool(name: str) -> Tool | None:
    return _TOOLS.get(name)


def read_tools() -> list[Tool]:
    return [t for t in _TOOLS.values() if t.kind is ToolKind.READ]


def write_tools() -> list[Tool]:
    return [t for t in _TOOLS.values() if t.kind is ToolKind.WRITE]


def all_tool_schemas() -> list[ToolSchema]:
    return [tool.schema() for tool in _TOOLS.values()]