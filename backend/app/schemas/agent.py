"""Agent, action-approval and observability schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: uuid.UUID | None = None
    # Optional structured hints; never trusted for authorization.
    context: dict[str, Any] = Field(default_factory=dict)


class ToolCallOut(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class AgentActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tool_name: str
    kind: str
    risk: str
    status: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    preview: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action_id: uuid.UUID
    decision: str
    note: str | None = None
    decided_at: datetime | None = None


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    # Optional edited arguments (for "Edit" then approve).
    edited_arguments: dict[str, Any] | None = None
    note: str | None = None


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    intent: str | None = None
    prompt: str
    model: str | None = None
    provider: str | None = None
    latency_ms: int | None = None
    total_tokens: int
    tool_call_count: int
    error: str | None = None
    created_at: datetime


class AgentRunDetail(BaseModel):
    run: AgentRunOut
    actions: list[AgentActionOut] = Field(default_factory=list)


# --- Streaming event protocol (SSE) -----------------------------------------
# Event kinds emitted to the client. Kept as simple strings for forward-compat.
#   run_started   – run id + metadata
#   status        – concise progress line ("Searching Outlook...")
#   tool_started  – a tool began
#   tool_result   – a tool finished (summary only)
#   action_pending – a write action requires approval (payload = AgentActionOut)
#   token         – a content delta (Markdown chunk)
#   message       – final assembled message
#   injection_warning – untrusted input flagged
#   error         – a safe error payload
#   run_finished  – final status + usage


class AgentEvent(BaseModel):
    kind: str
    data: dict[str, Any] = Field(default_factory=dict)


class ActivityEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    detail: str
    source: str | None = None
    level: str
    run_id: uuid.UUID | None = None
    created_at: datetime


class UsageOut(BaseModel):
    total_runs: int
    total_tokens: int
    avg_latency_ms: float
    total_tool_calls: int