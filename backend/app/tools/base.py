"""Tool abstraction for the agent runtime.

Tools are strongly typed with a JSON schema and separated into READ
(auto-executable) and WRITE (approval-gated). ``ToolContext`` carries the DB
session and resolved adapters; tools never import the agent.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import ToolSchema
from app.integrations.registry import ResolvedAdapters


class ToolKind(str, Enum):
    READ = "read"
    WRITE = "write"


class ToolRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolContext:
    session: AsyncSession
    organization_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str = ""
    user_name: str = ""
    adapters: ResolvedAdapters | None = None
    timezone: str = "UTC"


@dataclass
class ToolResult:
    ok: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    name: str
    description: str
    kind: ToolKind
    risk: ToolRisk = ToolRisk.LOW
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    def schema(self) -> ToolSchema:
        return ToolSchema(name=self.name, description=self.description, parameters=self.parameters)

    @abstractmethod
    async def run(self, ctx: ToolContext, **arguments: Any) -> ToolResult: ...