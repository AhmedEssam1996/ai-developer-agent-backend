"""Agent endpoints: streaming runs, run history, approvals, activity, realtime.

The agent streams via Server-Sent Events so the UI renders progress and Markdown
as it arrives. Write actions pause for approval; decisions are made here and the
approved action is executed by the executor.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import AgentRequest, run_agent
from app.api.deps import AuthContext, get_session, pagination, rate_limited
from app.auth.dependencies import get_auth_context
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.events.bus import event_bus
from app.models.agent import ActionApproval, AgentAction, AgentRun
from app.models.enums import ActionStatus
from app.models.integrations import Integration
from app.schemas.agent import (
    ActivityEventOut,
    AgentActionOut,
    AgentRunDetail,
    AgentRunOut,
    AgentRunRequest,
    ApprovalDecisionRequest,
    ApprovalOut,
    UsageOut,
)
from app.services import audit, integration_service
from app.services import activity as activity_service
from app.tools.base import ToolContext

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@router.post("/runs/stream")
async def stream_run(
    payload: AgentRunRequest,
    ctx: AuthContext = Depends(rate_limited),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Run the agent and stream events (SSE)."""
    request = AgentRequest(
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        user_email=ctx.user.email,
        user_name=ctx.user.display_name or ctx.user.full_name,
        timezone=ctx.user.timezone or "UTC",
        prompt=payload.message,
    )

    async def generator() -> AsyncIterator[str]:
        try:
            async for event in run_agent(session, request):
                yield _sse(event)
        except Exception:
            # The orchestrator already maps expected errors; this is a final net.
            yield _sse(
                {
                    "event": "error",
                    "data": {
                        "code": "agent_error",
                        "message": "The agent stopped unexpectedly. Please retry.",
                        "retryable": True,
                    },
                }
            )
        finally:
            await session.commit()
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs", response_model=list[AgentRunOut])
async def list_runs(
    limit: int = Query(default=25, ge=1, le=100),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[AgentRunOut]:
    rows = await session.scalars(
        select(AgentRun)
        .where(AgentRun.organization_id == ctx.organization_id)
        .order_by(desc(AgentRun.created_at))
        .limit(limit)
    )
    return [AgentRunOut.model_validate(r) for r in rows]


@router.get("/runs/{run_id}", response_model=AgentRunDetail)
async def get_run(
    run_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> AgentRunDetail:
    run = await session.get(AgentRun, run_id)
    if run is None or run.organization_id != ctx.organization_id:
        raise NotFoundError("Agent run not found.")
    actions = await session.scalars(
        select(AgentAction).where(AgentAction.run_id == run.id).order_by(AgentAction.sequence)
    )
    return AgentRunDetail(
        run=AgentRunOut.model_validate(run),
        actions=[_action_out(a) for a in actions],
    )


@router.get("/usage", response_model=UsageOut)
async def usage(
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> UsageOut:
    base = select(AgentRun).where(AgentRun.organization_id == ctx.organization_id)
    total_runs = int(await session.scalar(select(func.count()).select_from(base.subquery())) or 0)
    totals = await session.execute(
        select(
            func.coalesce(func.sum(AgentRun.total_tokens), 0),
            func.coalesce(func.avg(AgentRun.latency_ms), 0.0),
            func.coalesce(func.sum(AgentRun.tool_call_count), 0),
        ).where(AgentRun.organization_id == ctx.organization_id)
    )
    total_tokens, avg_latency, tool_calls = totals.one()
    return UsageOut(
        total_runs=total_runs,
        total_tokens=int(total_tokens or 0),
        avg_latency_ms=float(avg_latency or 0.0),
        total_tool_calls=int(tool_calls or 0),
    )


# --- Approvals ---------------------------------------------------------------

def _action_out(action: AgentAction) -> AgentActionOut:
    def _loads(value: str | None) -> dict:
        if not value:
            return {}
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {"value": loaded}
        except json.JSONDecodeError:
            return {}

    return AgentActionOut(
        id=action.id,
        tool_name=action.tool_name,
        kind=action.kind,
        risk=action.risk,
        status=action.status,
        arguments=_loads(action.arguments),
        preview=action.preview,
        result=_loads(action.result) if action.result else None,
        error=action.error,
        created_at=action.created_at,
    )


@router.get("/actions/pending", response_model=list[AgentActionOut])
async def pending_actions(
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[AgentActionOut]:
    rows = await session.scalars(
        select(AgentAction)
        .join(AgentRun, AgentRun.id == AgentAction.run_id)
        .where(
            AgentRun.organization_id == ctx.organization_id,
            AgentAction.status == ActionStatus.PENDING_APPROVAL.value,
        )
        .order_by(desc(AgentAction.created_at))
        .limit(50)
    )
    return [_action_out(a) for a in rows]


async def _resolve_adapters_for_org(session: AsyncSession, organization_id: uuid.UUID):
    try:
        return await integration_service.resolve_adapters(
            session, organization_id=organization_id
        )
    except Exception:
        return None


@router.post("/actions/{action_id}/decision", response_model=AgentActionOut)
async def decide_action(
    action_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    ctx: AuthContext = Depends(rate_limited),
    session: AsyncSession = Depends(get_session),
) -> AgentActionOut:
    action = await session.get(AgentAction, action_id)
    if action is None:
        raise NotFoundError("Action not found.")
    run = await session.get(AgentRun, action.run_id)
    if run is None or run.organization_id != ctx.organization_id:
        raise PermissionDeniedError("This action is not part of your organization.")

    approval = await session.scalar(
        select(ActionApproval).where(ActionApproval.action_id == action.id)
    )
    if approval is None:
        approval = ActionApproval(action_id=action.id, requested_by=ctx.user_id)
        session.add(approval)
        await session.flush()

    if payload.decision == "reject":
        approval.decision = "rejected"
        approval.decided_by = ctx.user_id
        approval.decided_at = datetime.now(timezone.utc)
        approval.note = payload.note
        action.status = ActionStatus.REJECTED.value
        await audit.record_audit(
            session,
            action="agent.action.rejected",
            user_id=ctx.user_id,
            organization_id=ctx.organization_id,
            target_type="agent_action",
            target_id=str(action.id),
        )
        await session.commit()
        return _action_out(action)

    # Approve (optionally with edited arguments).
    if payload.edited_arguments is not None:
        action.arguments = json.dumps(payload.edited_arguments, default=str)
    approval.decision = "approved"
    approval.decided_by = ctx.user_id
    approval.decided_at = datetime.now(timezone.utc)
    approval.note = payload.note
    if payload.edited_arguments is not None:
        approval.edited_arguments = json.dumps(payload.edited_arguments, default=str)
    action.status = ActionStatus.APPROVED.value
    await session.flush()

    adapters = await _resolve_adapters_for_org(session, ctx.organization_id)
    tool_ctx = ToolContext(
        session=session,
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        user_email=ctx.user.email,
        user_name=ctx.user.display_name or ctx.user.full_name,
        adapters=adapters,
        timezone=ctx.user.timezone or "UTC",
    )

    from app.agents.executor import execute_approved_action

    outcome = await execute_approved_action(session, action=action, ctx=tool_ctx)

    await audit.record_audit(
        session,
        action="agent.action.approved",
        user_id=ctx.user_id,
        organization_id=ctx.organization_id,
        target_type="agent_action",
        target_id=str(action.id),
        outcome="success" if outcome.ok else "failure",
        detail={"tool": action.tool_name},
    )
    await activity_service.record_activity(
        session,
        organization_id=ctx.organization_id,
        kind="action_executed" if outcome.ok else "action_failed",
        title=f"{'Executed' if outcome.ok else 'Failed'}: {action.tool_name}",
        detail=outcome.observation,
        level="info" if outcome.ok else "error",
        run_id=run.id,
    )
    await session.commit()
    return _action_out(action)


# --- Activity + realtime -----------------------------------------------------

@router.get("/activity", response_model=list[ActivityEventOut])
async def list_activity(
    limit: int = Query(default=50, ge=1, le=200),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[ActivityEventOut]:
    rows = await activity_service.list_activity(
        session, organization_id=ctx.organization_id, limit=limit
    )
    return [ActivityEventOut.model_validate(r) for r in rows]


@router.get("/events")
async def realtime_events(ctx: AuthContext = Depends(get_auth_context)) -> StreamingResponse:
    """SSE stream of realtime domain events for the organization."""
    return StreamingResponse(
        event_bus.stream(str(ctx.organization_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )