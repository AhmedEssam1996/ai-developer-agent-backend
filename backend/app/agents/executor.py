"""Tool execution with policy enforcement.

The executor is the only component that runs tools. It:

* evaluates policy (READ auto-run; WRITE requires approval),
* records an ``AgentAction`` (+ ``ActionApproval`` when needed),
* enforces idempotency via a per-call key,
* wraps untrusted tool output in a delimited envelope before it reaches the model,
* returns concise observations.

Approved write actions are executed via :func:`execute_approved_action`, which
is called by the approvals API after a human decision.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import policies
from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.models.agent import ActionApproval, AgentAction
from app.models.enums import ActionKind, ActionStatus, ToolRisk as ToolRiskEnum
from app.security.untrusted import scan_and_wrap
from app.tools import get_tool
from app.tools.base import ToolContext, ToolKind

logger = get_logger("app.agents.executor")


@dataclass
class ExecutionOutcome:
    action_id: uuid.UUID
    tool_name: str
    kind: str
    status: str
    ok: bool
    observation: str
    requires_approval: bool
    preview: str = ""


def _idempotency_key(run_id: uuid.UUID, tool_name: str, args: dict[str, Any]) -> str:
    import hashlib

    raw = f"{run_id}:{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def _wrap_result_for_model(tool_name: str, summary: str, data: dict[str, Any]) -> str:
    """Serialize a tool observation and wrap it as untrusted data."""
    payload = json.dumps({"summary": summary, "data": data}, default=str)
    wrapped, scan = scan_and_wrap(payload, source=tool_name)
    if scan.is_suspicious:
        logger.warning("Injection pattern in tool output from %s: %s", tool_name, scan.matched)
    return wrapped


async def execute_read_action(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    ctx: ToolContext,
    tool_name: str,
    arguments: dict[str, Any],
    sequence: int = 0,
) -> ExecutionOutcome:
    """Execute a READ tool and record it. READ tools never need approval."""
    tool = get_tool(tool_name)
    if tool is None:
        raise NotFoundError(f"Unknown tool: {tool_name}")

    decision = policies.evaluate(tool)
    if decision.requires_approval:
        # Should not happen for read tools, but never execute silently.
        raise AppError("Attempted to auto-run a tool that requires approval.")

    action = AgentAction(
        run_id=run_id,
        tool_name=tool_name,
        kind=ActionKind.READ.value,
        risk=ToolRiskEnum.READ.value,
        status=ActionStatus.EXECUTING.value,
        arguments=json.dumps(arguments, default=str),
        idempotency_key=_idempotency_key(run_id, tool_name, arguments),
        sequence=sequence,
    )
    session.add(action)
    await session.flush()

    try:
        result = await tool.run(ctx, **arguments)
        action.status = ActionStatus.EXECUTED.value if result.ok else ActionStatus.FAILED.value
        action.result = json.dumps(result.data, default=str)
        action.preview = result.summary
        action.error = None if result.ok else result.summary
        await session.flush()
        observation = _wrap_result_for_model(tool_name, result.summary, result.data)
        return ExecutionOutcome(
            action_id=action.id,
            tool_name=tool_name,
            kind=ActionKind.READ.value,
            status=action.status,
            ok=result.ok,
            observation=observation,
            requires_approval=False,
        )
    except Exception as exc:  # never leak raw exception text to the model
        action.status = ActionStatus.FAILED.value
        action.error = str(exc)[:500]
        await session.flush()
        logger.warning("Tool %s failed: %s", tool_name, exc)
        return ExecutionOutcome(
            action_id=action.id,
            tool_name=tool_name,
            kind=ActionKind.READ.value,
            status=action.status,
            ok=False,
            observation="The tool could not complete. Report this to the user politely.",
            requires_approval=False,
        )


async def propose_write_action(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    requested_by: uuid.UUID,
    ctx: ToolContext,
    tool_name: str,
    arguments: dict[str, Any],
    injection_flagged: bool = False,
    sequence: int = 0,
) -> ExecutionOutcome:
    """Record a WRITE tool as pending approval. Does not execute it."""
    tool = get_tool(tool_name)
    if tool is None:
        raise NotFoundError(f"Unknown tool: {tool_name}")

    decision = policies.evaluate(tool, injection_flagged=injection_flagged)
    # WRITE tools are never auto-run here regardless of policy outcome.
    decision_requires = True

    preview = ""
    if hasattr(tool, "preview"):
        try:
            preview = tool.preview(**arguments)  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - preview must never break
            preview = tool.description

    action = AgentAction(
        run_id=run_id,
        tool_name=tool_name,
        kind=ActionKind.WRITE.value,
        risk=(decision.risk or ToolRiskEnum.WRITE.value),
        status=ActionStatus.PENDING_APPROVAL.value,
        arguments=json.dumps(arguments, default=str),
        preview=preview,
        idempotency_key=_idempotency_key(run_id, tool_name, arguments),
        sequence=sequence,
    )
    session.add(action)
    await session.flush()

    approval = ActionApproval(
        action_id=action.id,
        requested_by=requested_by,
        decision="pending",
    )
    session.add(approval)
    await session.flush()

    return ExecutionOutcome(
        action_id=action.id,
        tool_name=tool_name,
        kind=ActionKind.WRITE.value,
        status=action.status,
        ok=True,
        observation=(
            f"Action '{tool_name}' is proposed and awaiting the user's approval."
        ),
        requires_approval=decision_requires,
        preview=preview,
    )


async def execute_approved_action(
    session: AsyncSession, *, action: AgentAction, ctx: ToolContext
) -> ExecutionOutcome:
    """Execute a WRITE action that has been approved by a human.

    Idempotent: if the action already executed, its stored result is returned.
    """
    if action.status == ActionStatus.EXECUTED.value:
        return ExecutionOutcome(
            action_id=action.id,
            tool_name=action.tool_name,
            kind=action.kind,
            status=action.status,
            ok=True,
            observation="This action was already executed.",
            requires_approval=False,
        )

    tool = get_tool(action.tool_name)
    if tool is None:
        raise NotFoundError(f"Unknown tool: {action.tool_name}")

    arguments = json.loads(action.arguments or "{}")
    action.status = ActionStatus.EXECUTING.value
    await session.flush()

    try:
        result = await tool.run(ctx, **arguments)
        action.status = ActionStatus.EXECUTED.value if result.ok else ActionStatus.FAILED.value
        action.result = json.dumps(result.data, default=str)
        action.error = None if result.ok else result.summary
        await session.flush()
        return ExecutionOutcome(
            action_id=action.id,
            tool_name=action.tool_name,
            kind=action.kind,
            status=action.status,
            ok=result.ok,
            observation=result.summary,
            requires_approval=False,
        )
    except Exception as exc:
        action.status = ActionStatus.FAILED.value
        action.error = str(exc)[:500]
        await session.flush()
        logger.warning("Approved action %s failed: %s", action.tool_name, exc)
        return ExecutionOutcome(
            action_id=action.id,
            tool_name=action.tool_name,
            kind=action.kind,
            status=action.status,
            ok=False,
            observation="The action failed after approval. Inform the user.",
            requires_approval=False,
        )