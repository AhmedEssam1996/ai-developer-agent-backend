"""Provider-agnostic AI interface used by the agent runtime.

The agent never imports OpenRouter directly. It depends on ``AIProvider`` so
the model/gateway can be swapped via configuration without touching agent
logic. ``get_provider`` returns the configured provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class AIMessage:
    role: str  # system | user | assistant | tool
    content: str = ""
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class StreamChunk:
    """A single streamed delta from the model."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


@dataclass
class ChatResult:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    model: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


class AIProvider(ABC):
    name: str = "base"
    model: str | None = None

    @abstractmethod
    async def stream_chat(
        self,
        *,
        messages: list[AIMessage],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion, yielding content/tool-call deltas."""

    @abstractmethod
    async def complete(
        self,
        *,
        messages: list[AIMessage],
        tools: list[ToolSchema] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        """Non-streaming completion (used for planning/structured steps)."""


def get_provider() -> AIProvider:
    from app.core.config import settings

    provider_name = (settings.ai_provider or "openrouter").lower()
    if provider_name == "openrouter":
        from app.ai.openrouter import OpenRouterProvider

        return OpenRouterProvider()
    raise ValueError(f"Unknown AI provider: {provider_name}")