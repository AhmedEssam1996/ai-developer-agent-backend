"""Tests for executor approve flow, adapter registry, and OpenRouter config."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents import executor
from app.core.config import settings
from app.integrations.base import (
    NormalizedEmail,
    NormalizedPerson,
)
from app.integrations.registry import (
    ResolvedAdapters,
    build_adapters,
    is_mock_mode,
    provider_configured,
)
from app.models.agent import ActionApproval, AgentAction
from app.models.enums import ActionKind, ActionStatus
from app.tools.base import ToolContext


def _ctx(session: Any, adapters: Any = None) -> ToolContext:
    return ToolContext(
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        session=session,
        adapters=adapters,
        access_token="test-token",
    )


# --- Executor approve logic -------------------------------------------------


class _DummyTool:
    name = "dummy_write"
    description = "d"
    kind = "write"

    async def run(self, ctx: ToolContext, **arguments: Any):  # pragma: no cover
        from app.tools.base import ToolResult

        return ToolResult(True, "ok", {})


class _DummyReadTool:
    name = "dummy_read"
    description = "d"
    kind = "read"

    async def run(self, ctx: ToolContext, **arguments: Any):  # pragma: no cover
        from app.tools.base import ToolResult

        return ToolResult(True, "ok", {})


@pytest.mark.anyio
async def test_propose_write_action_records_pending_approval(session) -> None:
    action, approval = await executor.propose_write_action(
        session,
        run_id=uuid.uuid4(),
        requested_by=uuid.uuid4(),
        ctx=_ctx(session),
        tool_name="dummy_write",
        arguments={"title": "test"},
    )
    assert action.status == ActionStatus.PENDING_APPROVAL.value
    assert action.kind == ActionKind.WRITE.value
    assert approval.decision == "pending"
    assert action.preview is not None


@pytest.mark.anyio
async def test_execute_approved_action_is_idempotent(session) -> None:
    run_id = uuid.uuid4()
    action = AgentAction(
        run_id=run_id,
        tool_name="dummy_write",
        kind=ActionKind.WRITE.value,
        status=ActionStatus.EXECUTED.value,
        arguments='{"title": "test"}',
        result='{"ok": true}',
    )
    session.add(action)
    await session.flush()

    outcome = await executor.execute_approved_action(session, action=action, ctx=_ctx(session))
    assert outcome.ok is True
    assert "already executed" in outcome.observation


@pytest.mark.anyio
async def test_execute_approved_action_runs_pending(session) -> None:
    run_id = uuid.uuid4()
    action = AgentAction(
        run_id=run_id,
        tool_name="dummy_write",
        kind=ActionKind.WRITE.value,
        status=ActionStatus.PENDING_APPROVAL.value,
        arguments='{"title": "test"}',
    )
    session.add(action)
    await session.flush()

    with patch("app.agents.executor.get_tool", return_value=_DummyTool()):
        outcome = await executor.execute_approved_action(
            session, action=action, ctx=_ctx(session)
        )
    assert outcome.ok is True
    assert action.status == ActionStatus.EXECUTED.value


@pytest.mark.anyio
async def test_execute_approved_action_marks_failure(session) -> None:
    run_id = uuid.uuid4()
    action = AgentAction(
        run_id=run_id,
        tool_name="dummy_write",
        kind=ActionKind.WRITE.value,
        status=ActionStatus.PENDING_APPROVAL.value,
        arguments='{"title": "test"}',
    )
    session.add(action)
    await session.flush()

    failing = MagicMock()
    failing.run = AsyncMock(side_effect=RuntimeError("boom"))
    with patch("app.agents.executor.get_tool", return_value=failing):
        outcome = await executor.execute_approved_action(
            session, action=action, ctx=_ctx(session)
        )
    assert outcome.ok is False
    assert action.status == ActionStatus.FAILED.value
    assert action.error is not None


# --- Registry / adapter resolution -----------------------------------------


def test_mock_mode_detection() -> None:
    assert is_mock_mode() is True


def test_provider_configured_in_mock() -> None:
    assert provider_configured("outlook") is True
    assert provider_configured("teams") is True
    assert provider_configured("goodday") is True
    assert provider_configured("unknown") is False


@pytest.mark.anyio
async def test_build_adapters_mock_returns_all_adapters() -> None:
    adapters = build_adapters(None)
    assert isinstance(adapters, ResolvedAdapters)
    assert adapters.is_mock is True
    assert adapters.source == "mock"
    assert adapters.mail is not None
    assert adapters.calendar is not None
    assert adapters.teams is not None
    assert adapters.tasks is not None
    assert adapters.directory is not None


@pytest.mark.anyio
async def test_mock_directory_adapter_returns_people() -> None:
    adapters = build_adapters(None)
    people = await adapters.directory.list_people()
    assert len(people) > 0
    assert all(isinstance(p, NormalizedPerson) for p in people)


@pytest.mark.anyio
async def test_mock_mail_adapter_returns_emails() -> None:
    adapters = build_adapters(None)
    emails = await adapters.mail.list_messages(top=10)
    assert len(emails) > 0
    assert all(isinstance(e, NormalizedEmail) for e in emails)


# --- OpenRouter base URL configuration --------------------------------------


def test_openrouter_uses_configured_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_base_url", "https://custom.example.com/v1")
    from app.ai import openrouter as ormod

    base = ormod._base_url()
    assert base == "https://custom.example.com/v1/chat/completions"


def test_openrouter_uses_default_base_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_base_url", None)
    from app.ai import openrouter as ormod

    base = ormod._base_url()
    assert base == "https://openrouter.ai/api/v1/chat/completions"


def test_openrouter_strips_trailing_slash(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openrouter_base_url", "https://custom.example.com/v1/")
    from app.ai import openrouter as ormod

    base = ormod._base_url()
    assert base == "https://custom.example.com/v1/chat/completions"